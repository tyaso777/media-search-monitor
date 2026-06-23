from __future__ import annotations

from news_monitor import database
from news_monitor.config import load_keywords, load_sites
from news_monitor.models import KeywordCandidate, ParsedResult


def test_import_keywords_and_sites(conn, repo_root):
    database.import_keywords(conn, load_keywords(repo_root / "config" / "keywords.csv")[:3])
    database.import_sites(conn, load_sites(repo_root / "config" / "sites.yaml")[:2])

    assert database.count_rows(conn, "keyword_groups") == 1
    assert database.count_rows(conn, "keyword_candidates") == 3
    assert database.count_rows(conn, "sites") == 2


def test_result_and_hit_upserts_are_url_and_candidate_scoped(imported_conn, repo_root):
    site = load_sites(repo_root / "config" / "sites.yaml")[0]
    keywords = database.enabled_keywords(imported_conn)
    result = ParsedResult(
        title="Same URL",
        url="https://example.com/article/1?utm_source=x&b=2&a=1#frag",
        published_date="2026-06-19",
        snippet="snippet",
    )

    item_id = database.upsert_result(imported_conn, site, result, result.url, "2026-06-19T00:00:00+00:00")
    database.upsert_hit(imported_conn, item_id, keywords[0], site.site_id, "run-1", "2026-06-19T00:00:00+00:00")
    item_id_again = database.upsert_result(
        imported_conn,
        site,
        ParsedResult("Same URL updated", "https://example.com/article/1?a=1&b=2", None, None),
        result.url,
        "2026-06-19T01:00:00+00:00",
    )
    database.upsert_hit(imported_conn, item_id_again, keywords[1], site.site_id, "run-1", "2026-06-19T01:00:00+00:00")

    assert item_id == item_id_again
    assert database.count_rows(imported_conn, "search_result_items") == 1
    assert database.count_rows(imported_conn, "search_result_hits") == 2


def test_import_keywords_migrates_legacy_ids(conn):
    legacy_keyword = KeywordCandidate(
        base_keyword_id="b001",
        base_keyword="Legacy Company",
        group_type="company",
        candidate_keyword_id="c001",
        candidate_keyword="Legacy",
        enabled=True,
        notes=None,
    )
    database.import_keywords(conn, [legacy_keyword])
    conn.execute(
        """
        INSERT INTO search_result_items (
            result_item_id, site_id, title, url, canonical_url, published_date,
            snippet, first_seen_at, last_seen_at, last_fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "item-1",
            "sample_news",
            "Title",
            "https://example.com/article",
            "https://example.com/article",
            None,
            None,
            "2026-06-19T00:00:00+09:00",
            "2026-06-19T00:00:00+09:00",
            "2026-06-19T00:00:00+09:00",
        ),
    )
    conn.execute(
        """
        INSERT INTO search_result_hits (
            hit_id, result_item_id, base_keyword_id, candidate_keyword_id, site_id,
            run_id, candidate_keyword, base_keyword, fetched_at, first_seen_at, last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "hit-1",
            "item-1",
            "b001",
            "c001",
            "sample_news",
            "run-1",
            "Legacy",
            "Legacy Company",
            "2026-06-19T00:00:00+09:00",
            "2026-06-19T00:00:00+09:00",
            "2026-06-19T00:00:00+09:00",
        ),
    )
    conn.commit()

    migrated_keyword = KeywordCandidate(
        base_keyword_id="kwg_abc123",
        base_keyword="Legacy Company",
        group_type="company",
        candidate_keyword_id="kwc_def456",
        candidate_keyword="Legacy",
        enabled=True,
        notes=None,
        source_base_keyword_id="b001",
        source_candidate_keyword_id="c001",
    )
    database.import_keywords(conn, [migrated_keyword])

    keywords = database.enabled_keywords(conn)
    hits = database.query_all(conn, "SELECT * FROM search_result_hits")
    assert [keyword["base_keyword_id"] for keyword in keywords] == ["kwg_abc123"]
    assert [keyword["candidate_keyword_id"] for keyword in keywords] == ["kwc_def456"]
    assert hits[0]["base_keyword_id"] == "kwg_abc123"
    assert hits[0]["candidate_keyword_id"] == "kwc_def456"
    assert conn.execute("SELECT COUNT(*) AS n FROM keyword_groups WHERE base_keyword_id='b001'").fetchone()["n"] == 0
    assert (
        conn.execute("SELECT COUNT(*) AS n FROM keyword_candidates WHERE candidate_keyword_id='c001'").fetchone()[
            "n"
        ]
        == 0
    )
