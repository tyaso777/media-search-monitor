"""SQLite persistence for news monitor."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from news_monitor.models import KeywordCandidate, ParsedResult, SiteConfig
from news_monitor.url_utils import canonicalize_url

T = TypeVar("T")
JST = timezone(timedelta(hours=9))
VIEWER_RESULT_CACHE_LIMIT_PER_GROUP = 5000
SITE_BACKOFF_DURATIONS = [
    timedelta(minutes=10),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(hours=12),
    timedelta(hours=24),
]


def connect(db_path: Path, busy_timeout_seconds: int = 30) -> sqlite3.Connection:
    """Open a SQLite connection with row dictionaries enabled."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=busy_timeout_seconds)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_seconds * 1000)}")
    if str(db_path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def main_database_path(conn: sqlite3.Connection) -> Path | None:
    """Return the filesystem path for the main database, if it has one."""

    row = conn.execute("PRAGMA database_list").fetchone()
    if row is None or not row["file"]:
        return None
    return Path(str(row["file"]))


def is_lock_error(exc: sqlite3.OperationalError) -> bool:
    """Return true when an OperationalError is a transient SQLite lock."""

    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message or "database is busy" in message


def run_with_lock_retry(
    conn: sqlite3.Connection,
    operation: Callable[[], T],
    retries: int,
    delay_seconds: float,
) -> T:
    """Run a database write operation, retrying transient SQLite lock failures."""

    attempt = 0
    while True:
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if not is_lock_error(exc) or attempt >= retries:
                raise
            conn.rollback()
            time.sleep(delay_seconds * (2**attempt))
            attempt += 1


def init_db(conn: sqlite3.Connection) -> None:
    """Create all database tables if they do not exist."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS keyword_groups (
            base_keyword_id TEXT PRIMARY KEY,
            base_keyword TEXT NOT NULL,
            group_type TEXT NOT NULL DEFAULT 'company',
            enabled INTEGER NOT NULL DEFAULT 1,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS keyword_candidates (
            candidate_keyword_id TEXT PRIMARY KEY,
            base_keyword_id TEXT NOT NULL,
            candidate_keyword TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            FOREIGN KEY(base_keyword_id) REFERENCES keyword_groups(base_keyword_id)
        );
        CREATE TABLE IF NOT EXISTS sites (
            site_id TEXT PRIMARY KEY,
            site_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            search_url_template TEXT NOT NULL,
            query_encoding TEXT NOT NULL DEFAULT 'utf-8',
            requires_playwright INTEGER NOT NULL DEFAULT 0,
            rate_limit_seconds INTEGER NOT NULL DEFAULT 3,
            config_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS search_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            error_message TEXT
        );
        CREATE TABLE IF NOT EXISTS search_result_items (
            result_item_id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            title TEXT,
            url TEXT NOT NULL,
            canonical_url TEXT NOT NULL,
            published_date TEXT,
            snippet TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            last_fetched_at TEXT NOT NULL,
            UNIQUE(site_id, canonical_url)
        );
        CREATE TABLE IF NOT EXISTS search_result_hits (
            hit_id TEXT PRIMARY KEY,
            result_item_id TEXT NOT NULL,
            base_keyword_id TEXT NOT NULL,
            candidate_keyword_id TEXT NOT NULL,
            site_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            candidate_keyword TEXT NOT NULL,
            base_keyword TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE(result_item_id, base_keyword_id, candidate_keyword_id)
        );
        CREATE TABLE IF NOT EXISTS fetch_errors (
            error_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            base_keyword_id TEXT,
            candidate_keyword_id TEXT,
            site_id TEXT,
            candidate_keyword TEXT,
            url TEXT,
            error_type TEXT NOT NULL,
            error_message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS crawl_skips (
            skip_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            site_id TEXT,
            base_keyword_id TEXT,
            candidate_keyword_id TEXT,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS site_crawl_backoff (
            site_id TEXT PRIMARY KEY,
            status_code INTEGER,
            error_type TEXT NOT NULL,
            error_message TEXT,
            failure_count INTEGER NOT NULL,
            backoff_until TEXT,
            last_failed_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS site_requests (
            request_id TEXT PRIMARY KEY,
            site_name TEXT NOT NULL,
            site_url TEXT NOT NULL,
            requester_name TEXT,
            requester_email TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            implementer_comment TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS keyword_change_requests (
            request_id TEXT PRIMARY KEY,
            request_type TEXT NOT NULL,
            group_type TEXT NOT NULL DEFAULT 'company',
            base_keyword TEXT NOT NULL,
            candidate_keyword TEXT,
            requester_name TEXT,
            requester_email TEXT,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            implementer_comment TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS viewer_group_summary (
            group_id TEXT PRIMARY KEY,
            group_name TEXT NOT NULL,
            group_type TEXT NOT NULL DEFAULT 'company',
            enabled INTEGER NOT NULL DEFAULT 1,
            article_count INTEGER NOT NULL DEFAULT 0,
            site_count INTEGER NOT NULL DEFAULT 0,
            latest_published_date TEXT,
            latest_hit_at TEXT,
            published_min_days INTEGER,
            hit_min_days INTEGER,
            sort_name TEXT NOT NULL,
            rebuilt_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_viewer_group_summary_type_name
            ON viewer_group_summary(group_type, enabled, sort_name);
        CREATE INDEX IF NOT EXISTS idx_viewer_group_summary_type_published
            ON viewer_group_summary(group_type, enabled, published_min_days, sort_name);
        CREATE INDEX IF NOT EXISTS idx_viewer_group_summary_type_hit
            ON viewer_group_summary(group_type, enabled, hit_min_days, sort_name);
        CREATE TABLE IF NOT EXISTS viewer_metadata (
            cache_name TEXT PRIMARY KEY,
            rebuilt_at TEXT NOT NULL,
            source_hit_count INTEGER NOT NULL DEFAULT 0,
            source_item_count INTEGER NOT NULL DEFAULT 0,
            row_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            error_message TEXT
        );
        CREATE TABLE IF NOT EXISTS viewer_result_rows (
            row_id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL,
            group_type TEXT NOT NULL DEFAULT 'company',
            result_item_id TEXT NOT NULL,
            cache_rank INTEGER NOT NULL,
            site_id TEXT NOT NULL,
            site_name TEXT NOT NULL,
            title TEXT,
            url TEXT NOT NULL,
            published_date TEXT,
            published_days INTEGER,
            first_hit_at TEXT NOT NULL,
            hit_days INTEGER,
            candidate_keywords TEXT NOT NULL,
            snippet TEXT,
            rebuilt_at TEXT NOT NULL,
            UNIQUE(group_id, result_item_id)
        );
        CREATE INDEX IF NOT EXISTS idx_viewer_result_rows_group_rank
            ON viewer_result_rows(group_id, cache_rank);
        CREATE INDEX IF NOT EXISTS idx_viewer_result_rows_group_published
            ON viewer_result_rows(group_id, published_days, cache_rank);
        CREATE INDEX IF NOT EXISTS idx_viewer_result_rows_group_hit
            ON viewer_result_rows(group_id, hit_days, cache_rank);
        CREATE TABLE IF NOT EXISTS viewer_group_site_filters (
            group_id TEXT NOT NULL,
            site_id TEXT NOT NULL,
            site_name TEXT NOT NULL,
            hit_count INTEGER NOT NULL DEFAULT 0,
            min_published_days INTEGER,
            min_hit_days INTEGER,
            rebuilt_at TEXT NOT NULL,
            PRIMARY KEY (group_id, site_id)
        );
        CREATE INDEX IF NOT EXISTS idx_viewer_group_site_filters_group
            ON viewer_group_site_filters(group_id, site_name);
        CREATE TABLE IF NOT EXISTS viewer_group_keyword_filters (
            group_id TEXT NOT NULL,
            candidate_keyword TEXT NOT NULL,
            hit_count INTEGER NOT NULL DEFAULT 0,
            min_published_days INTEGER,
            min_hit_days INTEGER,
            rebuilt_at TEXT NOT NULL,
            PRIMARY KEY (group_id, candidate_keyword)
        );
        CREATE INDEX IF NOT EXISTS idx_viewer_group_keyword_filters_group
            ON viewer_group_keyword_filters(group_id, candidate_keyword);
        """
    )
    _ensure_column(conn, "keyword_groups", "group_type", "TEXT NOT NULL DEFAULT 'company'")
    _ensure_column(conn, "viewer_group_summary", "enabled", "INTEGER NOT NULL DEFAULT 1")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column to an existing SQLite table when it is missing."""

    columns = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def import_keywords(conn: sqlite3.Connection, keywords: list[KeywordCandidate]) -> None:
    """Upsert keyword groups and candidate keywords."""

    for keyword in keywords:
        conn.execute(
            """
            INSERT INTO keyword_groups (base_keyword_id, base_keyword, group_type, enabled, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(base_keyword_id) DO UPDATE SET
                base_keyword = excluded.base_keyword,
                group_type = excluded.group_type,
                enabled = excluded.enabled,
                notes = excluded.notes
            """,
            (
                keyword.base_keyword_id,
                keyword.base_keyword,
                keyword.group_type,
                int(keyword.enabled),
                keyword.notes,
            ),
        )
        _migrate_keyword_group_id(conn, keyword)
        conn.execute(
            """
            INSERT INTO keyword_candidates (
                candidate_keyword_id, base_keyword_id, candidate_keyword, enabled, notes
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(candidate_keyword_id) DO UPDATE SET
                base_keyword_id = excluded.base_keyword_id,
                candidate_keyword = excluded.candidate_keyword,
                enabled = excluded.enabled,
                notes = excluded.notes
            """,
            (
                keyword.candidate_keyword_id,
                keyword.base_keyword_id,
                keyword.candidate_keyword,
                int(keyword.enabled),
                keyword.notes,
            ),
        )
        _migrate_keyword_candidate_id(conn, keyword)
    conn.commit()


def _migrate_keyword_group_id(conn: sqlite3.Connection, keyword: KeywordCandidate) -> None:
    """Move legacy base keyword references to the current internal ID."""

    old_id = keyword.source_base_keyword_id
    new_id = keyword.base_keyword_id
    if not old_id or old_id == new_id:
        return
    conn.execute(
        """
        UPDATE keyword_candidates
        SET base_keyword_id = ?
        WHERE base_keyword_id = ?
        """,
        (new_id, old_id),
    )
    for table in ("search_result_hits", "fetch_errors", "crawl_skips"):
        conn.execute(
            f"""
            UPDATE {table}
            SET base_keyword_id = ?
            WHERE base_keyword_id = ?
            """,
            (new_id, old_id),
        )
    conn.execute(
        """
        DELETE FROM keyword_groups
        WHERE base_keyword_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM keyword_candidates
              WHERE keyword_candidates.base_keyword_id = keyword_groups.base_keyword_id
          )
        """,
        (old_id,),
    )


def _migrate_keyword_candidate_id(conn: sqlite3.Connection, keyword: KeywordCandidate) -> None:
    """Move legacy candidate keyword references to the current internal ID."""

    old_id = keyword.source_candidate_keyword_id
    new_id = keyword.candidate_keyword_id
    if not old_id or old_id == new_id:
        return
    old_base_ids = [keyword.base_keyword_id]
    if keyword.source_base_keyword_id and keyword.source_base_keyword_id != keyword.base_keyword_id:
        old_base_ids.append(keyword.source_base_keyword_id)
    for old_base_id in old_base_ids:
        _merge_search_result_hits(
            conn,
            old_base_id,
            old_id,
            keyword.base_keyword_id,
            new_id,
            keyword.base_keyword,
            keyword.candidate_keyword,
        )
    for table in ("fetch_errors", "crawl_skips"):
        conn.execute(
            f"""
            UPDATE {table}
            SET base_keyword_id = ?, candidate_keyword_id = ?
            WHERE candidate_keyword_id = ?
            """,
            (keyword.base_keyword_id, new_id, old_id),
        )
    conn.execute("DELETE FROM keyword_candidates WHERE candidate_keyword_id = ?", (old_id,))


def _merge_search_result_hits(
    conn: sqlite3.Connection,
    old_base_id: str,
    old_candidate_id: str,
    new_base_id: str,
    new_candidate_id: str,
    base_keyword: str,
    candidate_keyword: str,
) -> None:
    """Merge existing hit rows from one keyword ID pair into another."""

    rows = list(
        conn.execute(
            """
            SELECT hit_id, result_item_id
            FROM search_result_hits
            WHERE base_keyword_id = ? AND candidate_keyword_id = ?
            """,
            (old_base_id, old_candidate_id),
        )
    )
    for row in rows:
        existing = conn.execute(
            """
            SELECT hit_id FROM search_result_hits
            WHERE result_item_id = ? AND base_keyword_id = ? AND candidate_keyword_id = ?
            """,
            (row["result_item_id"], new_base_id, new_candidate_id),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM search_result_hits WHERE hit_id = ?", (row["hit_id"],))
            continue
        conn.execute(
            """
            UPDATE search_result_hits
            SET base_keyword_id = ?,
                candidate_keyword_id = ?,
                base_keyword = ?,
                candidate_keyword = ?
            WHERE hit_id = ?
            """,
            (new_base_id, new_candidate_id, base_keyword, candidate_keyword, row["hit_id"]),
        )


def import_sites(conn: sqlite3.Connection, sites: list[SiteConfig]) -> None:
    """Upsert site definitions."""

    for site in sites:
        conn.execute(
            """
            INSERT INTO sites (
                site_id, site_name, enabled, search_url_template, query_encoding,
                requires_playwright, rate_limit_seconds, config_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(site_id) DO UPDATE SET
                site_name = excluded.site_name,
                enabled = excluded.enabled,
                search_url_template = excluded.search_url_template,
                query_encoding = excluded.query_encoding,
                requires_playwright = excluded.requires_playwright,
                rate_limit_seconds = excluded.rate_limit_seconds,
                config_json = excluded.config_json
            """,
            (
                site.site_id,
                site.site_name,
                int(site.enabled),
                site.search_url_template,
                site.query_encoding,
                int(site.requires_playwright),
                site.rate_limit_seconds,
                json.dumps(site.__dict__, ensure_ascii=False),
            ),
        )
    conn.commit()


def create_run(conn: sqlite3.Connection, started_at: str) -> str:
    """Create a search run and return its ID."""

    run_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO search_runs (run_id, started_at, status) VALUES (?, ?, ?)",
        (run_id, started_at, "running"),
    )
    conn.commit()
    return run_id


def finish_run(
    conn: sqlite3.Connection, run_id: str, finished_at: str, status: str, error_message: str | None = None
) -> None:
    """Mark a search run as finished."""

    conn.execute(
        """
        UPDATE search_runs
        SET finished_at = ?, status = ?, error_message = ?
        WHERE run_id = ?
        """,
        (finished_at, status, error_message, run_id),
    )
    conn.commit()


def enabled_keywords(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return enabled candidate keywords with their base keyword."""

    return list(
        conn.execute(
            """
            SELECT kg.base_keyword_id, kg.base_keyword, kc.candidate_keyword_id,
                   kc.candidate_keyword
            FROM keyword_candidates kc
            JOIN keyword_groups kg ON kg.base_keyword_id = kc.base_keyword_id
            WHERE kg.enabled = 1 AND kc.enabled = 1
            ORDER BY kg.base_keyword_id, kc.candidate_keyword_id
            """
        )
    )


def enabled_sites(conn: sqlite3.Connection) -> list[SiteConfig]:
    """Return enabled site definitions."""

    sites: list[SiteConfig] = []
    for row in conn.execute("SELECT config_json FROM sites WHERE enabled = 1 ORDER BY site_id"):
        sites.append(SiteConfig(**json.loads(row["config_json"])))
    return sites


def upsert_result(
    conn: sqlite3.Connection,
    site: SiteConfig,
    result: ParsedResult,
    page_url: str,
    fetched_at: str,
) -> str:
    """Upsert a URL-level search result item and return its ID."""

    canonical_url = canonicalize_url(result.url, page_url, site.site_id)
    result_item_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO search_result_items (
            result_item_id, site_id, title, url, canonical_url, published_date,
            snippet, first_seen_at, last_seen_at, last_fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(site_id, canonical_url) DO UPDATE SET
            title = COALESCE(excluded.title, search_result_items.title),
            url = excluded.url,
            published_date = COALESCE(excluded.published_date, search_result_items.published_date),
            snippet = COALESCE(excluded.snippet, search_result_items.snippet),
            last_seen_at = excluded.last_seen_at,
            last_fetched_at = excluded.last_fetched_at
        """,
        (
            result_item_id,
            site.site_id,
            result.title,
            result.url,
            canonical_url,
            result.published_date,
            result.snippet,
            fetched_at,
            fetched_at,
            fetched_at,
        ),
    )
    row = conn.execute(
        """
        SELECT result_item_id FROM search_result_items
        WHERE site_id = ? AND canonical_url = ?
        """,
        (site.site_id, canonical_url),
    ).fetchone()
    if row is None:  # pragma: no cover - defensive guard for unexpected SQLite behavior
        raise RuntimeError("Failed to upsert search result item")
    return str(row["result_item_id"])


def upsert_hit(
    conn: sqlite3.Connection,
    result_item_id: str,
    keyword: sqlite3.Row,
    site_id: str,
    run_id: str,
    fetched_at: str,
) -> None:
    """Upsert a keyword-level hit for a result item."""

    conn.execute(
        """
        INSERT INTO search_result_hits (
            hit_id, result_item_id, base_keyword_id, candidate_keyword_id, site_id,
            run_id, candidate_keyword, base_keyword, fetched_at, first_seen_at, last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(result_item_id, base_keyword_id, candidate_keyword_id) DO UPDATE SET
            run_id = excluded.run_id,
            fetched_at = excluded.fetched_at,
            last_seen_at = excluded.last_seen_at
        """,
        (
            uuid.uuid4().hex,
            result_item_id,
            keyword["base_keyword_id"],
            keyword["candidate_keyword_id"],
            site_id,
            run_id,
            keyword["candidate_keyword"],
            keyword["base_keyword"],
            fetched_at,
            fetched_at,
            fetched_at,
        ),
    )


def record_fetch_error(
    conn: sqlite3.Connection,
    run_id: str,
    created_at: str,
    error_type: str,
    error_message: str,
    site_id: str | None = None,
    keyword: sqlite3.Row | None = None,
    url: str | None = None,
) -> None:
    """Persist a fetch or parse error without aborting the whole run."""

    conn.execute(
        """
        INSERT INTO fetch_errors (
            error_id, run_id, base_keyword_id, candidate_keyword_id, site_id,
            candidate_keyword, url, error_type, error_message, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            run_id,
            keyword["base_keyword_id"] if keyword else None,
            keyword["candidate_keyword_id"] if keyword else None,
            site_id,
            keyword["candidate_keyword"] if keyword else None,
            url,
            error_type,
            error_message,
            created_at,
        ),
    )


def record_skip(
    conn: sqlite3.Connection,
    run_id: str,
    created_at: str,
    reason: str,
    site_id: str | None = None,
    keyword: sqlite3.Row | None = None,
) -> None:
    """Persist a non-error crawl skip."""

    conn.execute(
        """
        INSERT INTO crawl_skips (
            skip_id, run_id, site_id, base_keyword_id, candidate_keyword_id, reason, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            run_id,
            site_id,
            keyword["base_keyword_id"] if keyword else None,
            keyword["candidate_keyword_id"] if keyword else None,
            reason,
            created_at,
        ),
    )


def site_backoff_reason(status_code: int | None) -> str:
    """Return the crawl skip reason used for site-level throttling."""

    if status_code is None:
        return "site_backoff"
    return f"site_backoff_{status_code}"


def active_site_backoff(
    conn: sqlite3.Connection, site_id: str, now: str
) -> sqlite3.Row | None:
    """Return active site backoff row when the current time is before its retry time."""

    row = conn.execute(
        """
        SELECT site_id, status_code, error_type, error_message, failure_count,
               backoff_until, last_failed_at, updated_at
        FROM site_crawl_backoff
        WHERE site_id = ?
        """,
        (site_id,),
    ).fetchone()
    if row is None or not row["backoff_until"]:
        return None
    try:
        backoff_until = datetime.fromisoformat(str(row["backoff_until"]))
        now_dt = datetime.fromisoformat(now)
        if backoff_until > now_dt:
            return row
    except ValueError:
        if str(row["backoff_until"]) > now:
            return row
    return None


def record_site_backoff(
    conn: sqlite3.Connection,
    site_id: str,
    status_code: int | None,
    error_type: str,
    error_message: str,
    failed_at: str,
) -> None:
    """Record a transient site-level crawl stop and compute the next retry time."""

    current = conn.execute(
        "SELECT failure_count FROM site_crawl_backoff WHERE site_id = ?",
        (site_id,),
    ).fetchone()
    failure_count = int(current["failure_count"]) + 1 if current else 1
    duration = SITE_BACKOFF_DURATIONS[
        min(failure_count - 1, len(SITE_BACKOFF_DURATIONS) - 1)
    ]
    failed_dt = datetime.fromisoformat(failed_at)
    backoff_until = (failed_dt + duration).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO site_crawl_backoff (
            site_id, status_code, error_type, error_message, failure_count,
            backoff_until, last_failed_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(site_id) DO UPDATE SET
            status_code = excluded.status_code,
            error_type = excluded.error_type,
            error_message = excluded.error_message,
            failure_count = excluded.failure_count,
            backoff_until = excluded.backoff_until,
            last_failed_at = excluded.last_failed_at,
            updated_at = excluded.updated_at
        """,
        (
            site_id,
            status_code,
            error_type,
            error_message,
            failure_count,
            backoff_until,
            failed_at,
            failed_at,
        ),
    )


def clear_site_backoff(conn: sqlite3.Connection, site_id: str) -> None:
    """Clear site-level backoff after a successful fetch/persist cycle."""

    conn.execute("DELETE FROM site_crawl_backoff WHERE site_id = ?", (site_id,))


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    """Return row count for test and diagnostics use."""

    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
    return int(row["count"])


def query_all(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    """Return all rows for a query."""

    return list(conn.execute(sql, params))


def rebuild_viewer_cache(conn: sqlite3.Connection, now: datetime | None = None) -> None:
    """Rebuild pre-aggregated tables used by the desktop and localhost viewers."""

    rebuilt_at = (now or datetime.now(JST)).isoformat(timespec="seconds")
    today = _date_from_datetime(now) if now is not None else datetime.now(JST).date()
    rows = conn.execute(
        """
        SELECT
            kg.base_keyword_id AS group_id,
            kg.base_keyword AS group_name,
            COALESCE(kg.group_type, 'company') AS group_type,
            kg.enabled AS enabled,
            COUNT(DISTINCT i.result_item_id) AS article_count,
            COUNT(DISTINCT i.site_id) AS site_count,
            MAX(NULLIF(i.published_date, '')) AS latest_published_date,
            MAX(NULLIF(h.first_seen_at, '')) AS latest_hit_at
        FROM keyword_groups kg
        LEFT JOIN search_result_hits h ON h.base_keyword_id = kg.base_keyword_id
        LEFT JOIN search_result_items i ON i.result_item_id = h.result_item_id
        GROUP BY kg.base_keyword_id, kg.base_keyword, COALESCE(kg.group_type, 'company'), kg.enabled
        """
    ).fetchall()

    conn.execute("DELETE FROM viewer_group_summary")
    for row in rows:
        latest_published = row["latest_published_date"]
        latest_hit_at = row["latest_hit_at"]
        conn.execute(
            """
            INSERT INTO viewer_group_summary (
                group_id, group_name, group_type, enabled, article_count, site_count,
                latest_published_date, latest_hit_at, published_min_days, hit_min_days,
                sort_name, rebuilt_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["group_id"],
                row["group_name"],
                row["group_type"],
                int(row["enabled"] or 0),
                int(row["article_count"] or 0),
                int(row["site_count"] or 0),
                latest_published,
                latest_hit_at,
                _days_since(_parse_published_date(latest_published), today),
                _days_since(_parse_iso_date_prefix(latest_hit_at), today),
                row["group_name"],
                rebuilt_at,
            ),
        )

    source_hit_count = conn.execute("SELECT COUNT(*) AS n FROM search_result_hits").fetchone()["n"]
    source_item_count = conn.execute("SELECT COUNT(*) AS n FROM search_result_items").fetchone()["n"]
    result_row_count = _rebuild_viewer_result_rows(conn, rebuilt_at, today)
    site_filter_count = _rebuild_viewer_group_site_filters(conn, rebuilt_at, today)
    keyword_filter_count = _rebuild_viewer_group_keyword_filters(conn, rebuilt_at, today)
    conn.execute(
        """
        INSERT INTO viewer_metadata (
            cache_name, rebuilt_at, source_hit_count, source_item_count,
            row_count, status, error_message
        )
        VALUES ('group_summary', ?, ?, ?, ?, 'success', NULL)
        ON CONFLICT(cache_name) DO UPDATE SET
            rebuilt_at = excluded.rebuilt_at,
            source_hit_count = excluded.source_hit_count,
            source_item_count = excluded.source_item_count,
            row_count = excluded.row_count,
            status = excluded.status,
            error_message = excluded.error_message
        """,
        (rebuilt_at, source_hit_count, source_item_count, len(rows)),
    )
    conn.execute(
        """
        INSERT INTO viewer_metadata (
            cache_name, rebuilt_at, source_hit_count, source_item_count,
            row_count, status, error_message
        )
        VALUES ('result_rows', ?, ?, ?, ?, 'success', NULL)
        ON CONFLICT(cache_name) DO UPDATE SET
            rebuilt_at = excluded.rebuilt_at,
            source_hit_count = excluded.source_hit_count,
            source_item_count = excluded.source_item_count,
            row_count = excluded.row_count,
            status = excluded.status,
            error_message = excluded.error_message
        """,
        (rebuilt_at, source_hit_count, source_item_count, result_row_count),
    )
    conn.execute(
        """
        INSERT INTO viewer_metadata (
            cache_name, rebuilt_at, source_hit_count, source_item_count,
            row_count, status, error_message
        )
        VALUES ('filter_options', ?, ?, ?, ?, 'success', NULL)
        ON CONFLICT(cache_name) DO UPDATE SET
            rebuilt_at = excluded.rebuilt_at,
            source_hit_count = excluded.source_hit_count,
            source_item_count = excluded.source_item_count,
            row_count = excluded.row_count,
            status = excluded.status,
            error_message = excluded.error_message
        """,
        (rebuilt_at, source_hit_count, source_item_count, site_filter_count + keyword_filter_count),
    )
    conn.commit()


def _rebuild_viewer_result_rows(conn: sqlite3.Connection, rebuilt_at: str, today: date) -> int:
    """Flatten article rows for fast viewer paging."""

    rows = conn.execute(
        """
        SELECT
            h.base_keyword_id AS group_id,
            COALESCE(kg.group_type, 'company') AS group_type,
            i.result_item_id,
            i.site_id,
            COALESCE(s.site_name, i.site_id) AS site_name,
            i.title,
            i.url,
            i.published_date,
            MIN(h.first_seen_at) AS first_hit_at,
            GROUP_CONCAT(DISTINCT h.candidate_keyword) AS candidate_keywords,
            i.snippet
        FROM search_result_hits h
        JOIN search_result_items i ON i.result_item_id = h.result_item_id
        JOIN keyword_groups kg ON kg.base_keyword_id = h.base_keyword_id
        LEFT JOIN sites s ON s.site_id = i.site_id
        GROUP BY h.base_keyword_id, i.result_item_id
        ORDER BY
            h.base_keyword_id,
            CASE WHEN i.published_date IS NULL OR i.published_date = '' THEN 1 ELSE 0 END,
            i.published_date DESC,
            first_hit_at DESC
        """
    ).fetchall()

    conn.execute("DELETE FROM viewer_result_rows")
    rank_by_group: dict[str, int] = {}
    inserted = 0
    for row in rows:
        group_id = str(row["group_id"])
        rank = rank_by_group.get(group_id, 0) + 1
        rank_by_group[group_id] = rank
        if rank > VIEWER_RESULT_CACHE_LIMIT_PER_GROUP:
            continue

        published_date = row["published_date"]
        first_hit_at = row["first_hit_at"]
        conn.execute(
            """
            INSERT INTO viewer_result_rows (
                row_id, group_id, group_type, result_item_id, cache_rank,
                site_id, site_name, title, url, published_date, published_days,
                first_hit_at, hit_days, candidate_keywords, snippet, rebuilt_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                group_id,
                row["group_type"],
                row["result_item_id"],
                rank,
                row["site_id"],
                row["site_name"],
                row["title"],
                row["url"],
                published_date,
                _days_since(_parse_published_date(published_date), today),
                first_hit_at,
                _days_since(_parse_iso_date_prefix(first_hit_at), today),
                row["candidate_keywords"] or "",
                row["snippet"],
                rebuilt_at,
            ),
        )
        inserted += 1
    return inserted


def _rebuild_viewer_group_site_filters(
    conn: sqlite3.Connection, rebuilt_at: str, today: date
) -> int:
    """Pre-aggregate site filter options for each keyword group."""

    rows = conn.execute(
        """
        SELECT
            h.base_keyword_id AS group_id,
            i.site_id,
            COALESCE(s.site_name, i.site_id) AS site_name,
            COUNT(DISTINCT i.result_item_id) AS hit_count,
            MAX(NULLIF(i.published_date, '')) AS latest_published_date,
            MAX(NULLIF(h.first_seen_at, '')) AS latest_hit_at
        FROM search_result_hits h
        JOIN search_result_items i ON i.result_item_id = h.result_item_id
        JOIN keyword_groups kg ON kg.base_keyword_id = h.base_keyword_id
        LEFT JOIN sites s ON s.site_id = i.site_id
        GROUP BY h.base_keyword_id, i.site_id, COALESCE(s.site_name, i.site_id)
        ORDER BY h.base_keyword_id, site_name
        """
    ).fetchall()

    conn.execute("DELETE FROM viewer_group_site_filters")
    for row in rows:
        conn.execute(
            """
            INSERT INTO viewer_group_site_filters (
                group_id, site_id, site_name, hit_count,
                min_published_days, min_hit_days, rebuilt_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["group_id"],
                row["site_id"],
                row["site_name"],
                int(row["hit_count"] or 0),
                _days_since(_parse_published_date(row["latest_published_date"]), today),
                _days_since(_parse_iso_date_prefix(row["latest_hit_at"]), today),
                rebuilt_at,
            ),
        )
    return len(rows)


def _rebuild_viewer_group_keyword_filters(
    conn: sqlite3.Connection, rebuilt_at: str, today: date
) -> int:
    """Pre-aggregate candidate keyword filter options for each keyword group."""

    rows = conn.execute(
        """
        SELECT
            h.base_keyword_id AS group_id,
            h.candidate_keyword,
            COUNT(DISTINCT h.result_item_id) AS hit_count,
            MAX(NULLIF(i.published_date, '')) AS latest_published_date,
            MAX(NULLIF(h.first_seen_at, '')) AS latest_hit_at
        FROM search_result_hits h
        JOIN search_result_items i ON i.result_item_id = h.result_item_id
        JOIN keyword_groups kg ON kg.base_keyword_id = h.base_keyword_id
        GROUP BY h.base_keyword_id, h.candidate_keyword
        ORDER BY h.base_keyword_id, h.candidate_keyword
        """
    ).fetchall()

    conn.execute("DELETE FROM viewer_group_keyword_filters")
    for row in rows:
        conn.execute(
            """
            INSERT INTO viewer_group_keyword_filters (
                group_id, candidate_keyword, hit_count,
                min_published_days, min_hit_days, rebuilt_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row["group_id"],
                row["candidate_keyword"],
                int(row["hit_count"] or 0),
                _days_since(_parse_published_date(row["latest_published_date"]), today),
                _days_since(_parse_iso_date_prefix(row["latest_hit_at"]), today),
                rebuilt_at,
            ),
        )
    return len(rows)


def _date_from_datetime(value: datetime) -> date:
    """Return the local date for a datetime, preserving naive values as-is."""

    if value.tzinfo is None:
        return value.date()
    return value.astimezone(JST).date()


def _parse_published_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y/%m/%d").date()
    except ValueError:
        return None


def _parse_iso_date_prefix(value: str | None) -> date | None:
    if not value or len(value) < 10:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_since(value: date | None, today: date) -> int | None:
    if value is None:
        return None
    return (today - value).days
