from __future__ import annotations

from news_monitor import database
from news_monitor.config import load_sites
from news_monitor.models import ParsedResult
from news_monitor.reporter import generate_report


def test_report_groups_duplicate_url_and_lists_candidate_keywords(imported_conn, repo_root, tmp_path):
    site = load_sites(repo_root / "config" / "sites.yaml")[0]
    keywords = database.enabled_keywords(imported_conn)
    item_id = database.upsert_result(
        imported_conn,
        site,
        ParsedResult("Grouped Item", "https://example.com/article/1", "2026-06-19", "snippet"),
        "https://example.com/search?q=x",
        "2026-06-19T10:00:00+00:00",
    )
    database.upsert_hit(imported_conn, item_id, keywords[0], site.site_id, "run-1", "2026-06-19T10:00:00+00:00")
    database.upsert_hit(imported_conn, item_id, keywords[1], site.site_id, "run-1", "2026-06-19T10:00:00+00:00")
    imported_conn.commit()

    report_path = generate_report(imported_conn, "2026-06-19", tmp_path)
    html = report_path.read_text(encoding="utf-8")

    assert "Grouped Item" in html
    assert "トヨタ自動車" in html
    assert "トヨタ" in html
    assert "<table>" in html
    assert 'id="companyFilter"' in html
    assert 'id="fromFilter"' in html
    assert 'id="toFilter"' in html
    assert (
        html.count(
            '<td class="title-cell"><a href="https://example.com/article/1" target="_blank" '
            'rel="noopener noreferrer">Grouped Item</a></td>'
        )
        == 1
    )
