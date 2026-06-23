"""HTML report generation."""

from __future__ import annotations

import html
import sqlite3
from pathlib import Path


def generate_report(conn: sqlite3.Connection, report_date: str, output_dir: Path) -> Path:
    """Generate a standalone HTML report for new results on a date."""

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        SELECT
            h.base_keyword,
            h.candidate_keyword,
            i.site_id,
            s.site_name,
            i.title,
            i.url,
            i.published_date,
            i.snippet,
            i.first_seen_at,
            i.last_fetched_at,
            i.canonical_url
        FROM search_result_items i
        JOIN search_result_hits h ON h.result_item_id = i.result_item_id
        LEFT JOIN sites s ON s.site_id = i.site_id
        WHERE substr(i.first_seen_at, 1, 10) = ?
        ORDER BY h.base_keyword, s.site_name, i.title, h.candidate_keyword
        """,
        (report_date,),
    ).fetchall()

    items = _group_rows(rows)
    report_path = output_dir / f"{report_date}_new_results.html"
    report_path.write_text(_render_html(report_date, items), encoding="utf-8")
    return report_path


def _group_rows(rows: list[sqlite3.Row]) -> list[dict[str, object]]:
    """Group duplicate URL hits and aggregate candidate keywords."""

    grouped: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        site_name = row["site_name"] or row["site_id"]
        key = (row["base_keyword"], site_name, row["canonical_url"])
        item = grouped.setdefault(
            key,
            {
                "base_keyword": row["base_keyword"],
                "site_name": site_name,
                "title": row["title"],
                "url": row["url"],
                "published_date": row["published_date"],
                "snippet": row["snippet"],
                "last_fetched_at": row["last_fetched_at"],
                "candidate_keywords": [],
            },
        )
        candidates = item["candidate_keywords"]
        assert isinstance(candidates, list)
        if row["candidate_keyword"] not in candidates:
            candidates.append(row["candidate_keyword"])
    return list(grouped.values())


def _render_html(report_date: str, items: list[dict[str, object]]) -> str:
    """Render report data as a filterable standalone HTML table."""

    companies = sorted({str(item["base_keyword"]) for item in items})
    company_options = "".join(
        f"<option value=\"{html.escape(company)}\">{html.escape(company)}</option>"
        for company in companies
    )
    rows_html = "\n".join(_render_row(item) for item in items)
    initial_count = len(items)

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>New Search Results {html.escape(report_date)}</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    body {{
      margin: 0;
      background: #f7f7f5;
      color: #222;
      height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid #d8d8d2;
      padding: 20px 28px 16px;
      flex: 0 0 auto;
    }}
    h1 {{
      font-size: 24px;
      line-height: 1.25;
      margin: 0 0 14px;
    }}
    .filters {{
      display: grid;
      grid-template-columns: minmax(180px, 1.2fr) minmax(160px, 1fr) minmax(150px, .9fr) minmax(150px, .9fr) minmax(220px, 1.4fr);
      gap: 10px;
      align-items: end;
    }}
    label {{
      display: grid;
      gap: 4px;
      font-size: 12px;
      font-weight: 700;
      color: #444;
    }}
    input, select {{
      border: 1px solid #bdbdb6;
      border-radius: 6px;
      font: inherit;
      min-height: 34px;
      padding: 5px 8px;
      background: #fff;
    }}
    .summary {{
      color: #555;
      font-size: 13px;
      margin-top: 10px;
    }}
    main {{
      flex: 1 1 auto;
      min-height: 0;
      padding: 18px 28px 32px;
    }}
    .table-wrap {{
      height: 100%;
      overflow: auto;
      border: 1px solid #d8d8d2;
      background: #fff;
    }}
    table {{
      border-collapse: collapse;
      min-width: 1180px;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid #e5e5df;
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #efefea;
      font-size: 12px;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    td {{
      font-size: 13px;
    }}
    .title-cell {{
      min-width: 320px;
      max-width: 520px;
    }}
    .url-cell, .snippet-cell {{
      overflow-wrap: anywhere;
    }}
    .muted {{
      color: #666;
      font-size: 12px;
    }}
    a {{
      color: #064f8f;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    tr[hidden] {{
      display: none;
    }}
    @media (max-width: 900px) {{
      header {{
        padding: 14px 12px 12px;
      }}
      .filters {{
        grid-template-columns: 1fr;
      }}
      main {{
        padding: 12px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>New Search Results: {html.escape(report_date)}</h1>
    <div class="filters">
      <label>会社名
        <select id="companyFilter">
          <option value="">すべて</option>
          {company_options}
        </select>
      </label>
      <label>サイト名
        <input id="siteFilter" type="search" placeholder="例: 朝日">
      </label>
      <label>取得日時 From
        <input id="fromFilter" type="datetime-local">
      </label>
      <label>取得日時 To
        <input id="toFilter" type="datetime-local">
      </label>
      <label>全文検索
        <input id="textFilter" type="search" placeholder="タイトル・URL・スニペット">
      </label>
    </div>
    <div class="summary"><span id="visibleCount">{initial_count}</span> / <span id="totalCount">{initial_count}</span> 件</div>
  </header>
  <main>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>会社名</th>
            <th>サイト</th>
            <th>タイトル</th>
            <th>掲載日</th>
            <th>取得日時</th>
            <th>候補キーワード</th>
            <th>URL</th>
            <th>スニペット</th>
          </tr>
        </thead>
        <tbody id="resultRows">
          {rows_html or '<tr><td colspan="8">No new results.</td></tr>'}
        </tbody>
      </table>
    </div>
  </main>
  <script>
    const rows = Array.from(document.querySelectorAll("#resultRows tr[data-company]"));
    const controls = ["companyFilter", "siteFilter", "fromFilter", "toFilter", "textFilter"]
      .map((id) => document.getElementById(id));
    const visibleCount = document.getElementById("visibleCount");

    function normalize(value) {{
      return String(value || "").toLowerCase();
    }}

    function applyFilters() {{
      const company = document.getElementById("companyFilter").value;
      const site = normalize(document.getElementById("siteFilter").value);
      const text = normalize(document.getElementById("textFilter").value);
      const from = document.getElementById("fromFilter").value;
      const to = document.getElementById("toFilter").value;
      let visible = 0;

      rows.forEach((row) => {{
        const rowCompany = row.dataset.company || "";
        const rowSite = normalize(row.dataset.site);
        const rowFetched = row.dataset.fetchedLocal || "";
        const rowText = normalize(row.dataset.searchText);
        const matched =
          (!company || rowCompany === company) &&
          (!site || rowSite.includes(site)) &&
          (!from || rowFetched >= from) &&
          (!to || rowFetched <= to) &&
          (!text || rowText.includes(text));
        row.hidden = !matched;
        if (matched) visible += 1;
      }});

      visibleCount.textContent = String(visible);
    }}

    controls.forEach((control) => control.addEventListener("input", applyFilters));
  </script>
</body>
</html>
"""


def _render_row(item: dict[str, object]) -> str:
    """Render one grouped result row."""

    company = str(item["base_keyword"])
    site = str(item["site_name"])
    title = str(item["title"] or "(untitled)")
    url = str(item["url"])
    published_date = str(item["published_date"] or "")
    snippet = str(item["snippet"] or "")
    fetched = str(item["last_fetched_at"] or "")
    fetched_local = fetched[:16]
    candidates = ", ".join(str(v) for v in item["candidate_keywords"])
    search_text = " ".join([company, site, title, url, published_date, snippet, candidates])

    return (
        f"<tr data-company=\"{html.escape(company)}\" "
        f"data-site=\"{html.escape(site)}\" "
        f"data-fetched-local=\"{html.escape(fetched_local)}\" "
        f"data-search-text=\"{html.escape(search_text)}\">"
        f"<td>{html.escape(company)}</td>"
        f"<td>{html.escape(site)}</td>"
        f"<td class=\"title-cell\"><a href=\"{html.escape(url)}\" target=\"_blank\" rel=\"noopener noreferrer\">{html.escape(title)}</a></td>"
        f"<td>{html.escape(published_date)}</td>"
        f"<td>{html.escape(fetched)}</td>"
        f"<td>{html.escape(candidates)}</td>"
        f"<td class=\"url-cell\"><a href=\"{html.escape(url)}\" target=\"_blank\" rel=\"noopener noreferrer\">{html.escape(url)}</a></td>"
        f"<td class=\"snippet-cell muted\">{html.escape(snippet)}</td>"
        "</tr>"
    )
