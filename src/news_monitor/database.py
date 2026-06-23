"""SQLite persistence for news monitor."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable, TypeVar

from news_monitor.models import KeywordCandidate, ParsedResult, SiteConfig
from news_monitor.url_utils import canonicalize_url

T = TypeVar("T")


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
        """
    )
    _ensure_column(conn, "keyword_groups", "group_type", "TEXT NOT NULL DEFAULT 'company'")
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

    canonical_url = canonicalize_url(result.url, page_url)
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


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    """Return row count for test and diagnostics use."""

    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
    return int(row["count"])


def query_all(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    """Return all rows for a query."""

    return list(conn.execute(sql, params))
