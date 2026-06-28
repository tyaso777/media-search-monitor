from __future__ import annotations

from datetime import datetime

from news_monitor import database
from news_monitor.config import load_keywords, load_sites
from news_monitor.models import KeywordCandidate, ParsedResult, SiteConfig


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


def test_rebuild_viewer_cache_summarizes_keyword_groups(conn):
    keyword = KeywordCandidate(
        base_keyword_id="kwg_company",
        base_keyword="Example Company",
        group_type="company",
        candidate_keyword_id="kwc_example",
        candidate_keyword="Example",
        enabled=True,
        notes=None,
    )
    another_candidate = KeywordCandidate(
        base_keyword_id="kwg_company",
        base_keyword="Example Company",
        group_type="company",
        candidate_keyword_id="kwc_example_alt",
        candidate_keyword="Example Alt",
        enabled=True,
        notes=None,
    )
    topic = KeywordCandidate(
        base_keyword_id="kwg_topic",
        base_keyword="生成AI",
        group_type="topic",
        candidate_keyword_id="kwc_topic",
        candidate_keyword="生成AI",
        enabled=True,
        notes=None,
    )
    database.import_keywords(conn, [keyword, another_candidate, topic])
    database.import_sites(
        conn,
        [
            SiteConfig(
                site_id="site-a",
                site_name="Site A",
                enabled=True,
                search_url_template="https://example.com/search?q={query}",
                query_encoding="utf-8",
                requires_playwright=False,
                result_item_selector=".result",
                title_selector="a",
                url_selector="a",
                date_selector=".date",
                snippet_selector=None,
                rate_limit_seconds=1,
                user_agent="test",
                max_pages=1,
                next_page_selector=None,
            ),
            SiteConfig(
                site_id="site-b",
                site_name="Site B",
                enabled=True,
                search_url_template="https://example.com/search?q={query}",
                query_encoding="utf-8",
                requires_playwright=False,
                result_item_selector=".result",
                title_selector="a",
                url_selector="a",
                date_selector=".date",
                snippet_selector=None,
                rate_limit_seconds=1,
                user_agent="test",
                max_pages=1,
                next_page_selector=None,
            ),
        ],
    )
    conn.execute(
        """
        INSERT INTO search_result_items (
            result_item_id, site_id, title, url, canonical_url, published_date,
            snippet, first_seen_at, last_seen_at, last_fetched_at
        )
        VALUES
            ('item-1', 'site-a', 'Title 1', 'https://example.com/1', 'https://example.com/1', '2026/06/25', NULL, '2026-06-25T09:00:00+09:00', '2026-06-25T09:00:00+09:00', '2026-06-25T09:00:00+09:00'),
            ('item-2', 'site-b', 'Title 2', 'https://example.com/2', 'https://example.com/2', '2026/06/24', NULL, '2026-06-24T09:00:00+09:00', '2026-06-24T09:00:00+09:00', '2026-06-24T09:00:00+09:00')
        """
    )
    conn.execute(
        """
        INSERT INTO search_result_hits (
            hit_id, result_item_id, base_keyword_id, candidate_keyword_id, site_id,
            run_id, candidate_keyword, base_keyword, fetched_at, first_seen_at, last_seen_at
        )
        VALUES
            ('hit-1', 'item-1', 'kwg_company', 'kwc_example', 'site-a', 'run-1', 'Example', 'Example Company', '2026-06-26T10:00:00+09:00', '2026-06-26T10:00:00+09:00', '2026-06-26T10:00:00+09:00'),
            ('hit-2', 'item-1', 'kwg_company', 'kwc_example_alt', 'site-a', 'run-1', 'Example Alt', 'Example Company', '2026-06-26T10:00:00+09:00', '2026-06-26T10:00:00+09:00', '2026-06-26T10:00:00+09:00'),
            ('hit-3', 'item-2', 'kwg_topic', 'kwc_topic', 'site-b', 'run-1', '生成AI', '生成AI', '2026-06-24T10:00:00+09:00', '2026-06-24T10:00:00+09:00', '2026-06-24T10:00:00+09:00')
        """
    )
    conn.commit()

    database.rebuild_viewer_cache(conn, now=datetime.fromisoformat("2026-06-27T12:00:00+09:00"))

    company = conn.execute(
        "SELECT * FROM viewer_group_summary WHERE group_id = 'kwg_company'"
    ).fetchone()
    result_row = conn.execute(
        "SELECT * FROM viewer_result_rows WHERE group_id = 'kwg_company'"
    ).fetchone()
    topic_row = conn.execute("SELECT * FROM viewer_group_summary WHERE group_id = 'kwg_topic'").fetchone()
    metadata = conn.execute("SELECT * FROM viewer_metadata WHERE cache_name = 'group_summary'").fetchone()
    result_metadata = conn.execute("SELECT * FROM viewer_metadata WHERE cache_name = 'result_rows'").fetchone()
    filter_metadata = conn.execute("SELECT * FROM viewer_metadata WHERE cache_name = 'filter_options'").fetchone()
    site_filter = conn.execute(
        "SELECT * FROM viewer_group_site_filters WHERE group_id = 'kwg_company'"
    ).fetchone()
    keyword_filters = conn.execute(
        "SELECT candidate_keyword, hit_count FROM viewer_group_keyword_filters WHERE group_id = 'kwg_company' ORDER BY candidate_keyword"
    ).fetchall()

    assert company["group_type"] == "company"
    assert company["enabled"] == 1
    assert company["article_count"] == 1
    assert company["site_count"] == 1
    assert company["latest_published_date"] == "2026/06/25"
    assert company["published_min_days"] == 2
    assert company["hit_min_days"] == 1
    assert result_row["result_item_id"] == "item-1"
    assert result_row["cache_rank"] == 1
    assert result_row["published_days"] == 2
    assert result_row["hit_days"] == 1
    assert result_row["candidate_keywords"] in ("Example,Example Alt", "Example Alt,Example")
    assert topic_row["group_type"] == "topic"
    assert topic_row["enabled"] == 1
    assert metadata["source_hit_count"] == 3
    assert metadata["source_item_count"] == 2
    assert metadata["row_count"] == 2
    assert result_metadata["row_count"] == 2
    assert filter_metadata["row_count"] == 5
    assert site_filter["site_id"] == "site-a"
    assert site_filter["hit_count"] == 1
    assert site_filter["min_published_days"] == 2
    assert site_filter["min_hit_days"] == 1
    assert [(row["candidate_keyword"], row["hit_count"]) for row in keyword_filters] == [
        ("Example", 1),
        ("Example Alt", 1),
    ]
