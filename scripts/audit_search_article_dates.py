"""Audit search-result and article-page published-date availability per site."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from news_monitor.config import load_sites
from news_monitor.date_utils import normalize_published_date
from news_monitor.models import SiteConfig
from news_monitor.parser import parse_article_published_date, parse_search_results
from news_monitor.url_utils import encode_query


ROOT = Path(__file__).resolve().parents[1]
QUERY = "トヨタ"
REQUEST_TIMEOUT = 20


def build_search_url(site: SiteConfig) -> str:
    """Return the actual search URL for the audit query."""

    return site.search_url_template.format(query=encode_query(QUERY, site.query_encoding))


def fetch_http(client: httpx.Client, url: str) -> tuple[str, str, int]:
    """Fetch one URL with httpx."""

    response = client.get(url)
    return response.text, str(response.url), response.status_code


def fetch_playwright(url: str) -> tuple[str, str, int | None]:
    """Fetch one URL with Playwright when the site requires rendered results."""

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(url, wait_until="networkidle", timeout=REQUEST_TIMEOUT * 1000)
        page.wait_for_timeout(1500)
        html = page.content()
        final_url = page.url
        status = response.status if response else None
        browser.close()
    return html, final_url, status


def fetch_search_page(client: httpx.Client, site: SiteConfig, url: str) -> tuple[str, str, int | None, str]:
    """Fetch a search page using the method configured for the site."""

    if site.requires_playwright:
        try:
            html, final_url, status = fetch_playwright(url)
            return html, final_url, status, "playwright"
        except Exception:
            html, final_url, status = fetch_http(client, url)
            return html, final_url, status, "httpx-after-playwright-failure"
    html, final_url, status = fetch_http(client, url)
    return html, final_url, status, "httpx"


def normalize_date(value: str | None, site: SiteConfig) -> str | None:
    """Normalize a date candidate for the site's configured rule."""

    return normalize_published_date(value, None, site.date_rule)


def first_article_with_or_without_search_date(results, site: SiteConfig):
    """Return a representative article for fallback checks."""

    if not results:
        return None
    sorted_results = sorted(
        results,
        key=lambda result: 0 if looks_like_article_url(result.url, site) else 1,
    )
    for result in sorted_results:
        if not normalize_date(result.published_date, site):
            return result
    return sorted_results[0]


def looks_like_article_url(url: str | None, site: SiteConfig) -> bool:
    """Return whether a URL looks like an individual article page."""

    if not url:
        return False
    if site.site_id == "nikkan_kogyo":
        return "/articles/view/" in url
    if site.site_id == "logistics_today":
        return (
            "logi-today.com/" in url
            and "/category/" not in url
            and "/?s=" not in url
            and not url.rstrip("/").endswith("logi-today.com")
        )
    if site.site_id == "ryutsuu_biz":
        return re_match_url(url, r"/[a-z]/\d{6,}\.html$")
    if site.site_id == "nikkan_jidosha":
        return "/archives/" in url and "/archives/tag/" not in url and "/archives/category/" not in url
    if site.site_id == "kyodo":
        return "/news/" in url and not url.rstrip("/").endswith("/news")
    if site.site_id == "shokuhin_sangyo":
        return re_match_url(url, r"/\d{4}/\d{2}/\d{2}/")
    if site.site_id == "chemical_daily":
        return re_match_url(url, r"/archives/\d+")
    article_markers = [
        "/article/",
        "/articles/",
        "/articles/-/",
        "/item/",
        "/entry-",
        "/article/detail/",
        "/archives/",
        "/news/article.jsp",
        "go.php?go=",
    ]
    bad_markers = [
        "/search",
        "?s=",
        "/tag/",
        "/category/",
        "/about",
        "/company",
        "/news/",
        "/index",
        "/topics/",
        "/sections/",
    ]
    if any(marker in url for marker in bad_markers):
        return False
    return any(marker in url for marker in article_markers)


def re_match_url(url: str, pattern: str) -> bool:
    """Small regex helper kept local to avoid importing re at module top for one use."""

    import re

    return re.search(pattern, url) is not None


def audit_site(client: httpx.Client, site: SiteConfig) -> dict[str, Any]:
    """Audit one configured site."""

    search_url = build_search_url(site)
    row: dict[str, Any] = {
        "site_id": site.site_id,
        "site_name": site.site_name,
        "requires_playwright": site.requires_playwright,
        "search_url": search_url,
        "fetch_method": None,
        "search_status": None,
        "search_final_url": None,
        "parser_strategy": site.parser_strategy,
        "date_strategy": site.date_strategy,
        "date_rule": site.date_rule,
        "result_item_selector": site.result_item_selector,
        "date_selector": site.date_selector,
        "search_result_count": 0,
        "search_dated_count": 0,
        "search_date_available": False,
        "search_date_raw_example": None,
        "search_date_normalized_example": None,
        "search_article_url_example": None,
        "search_title_example": None,
        "article_url_example": None,
        "article_url_looks_valid": False,
        "article_status": None,
        "article_date_available": False,
        "article_date_raw_example": None,
        "article_date_normalized_example": None,
        "article_date_source": "common_article_meta_or_time",
        "search_error": None,
        "article_error": None,
        "judgement": None,
        "site_config": asdict(site),
    }
    try:
        html, final_url, status, fetch_method = fetch_search_page(client, site, search_url)
        row["fetch_method"] = fetch_method
        row["search_status"] = status
        row["search_final_url"] = final_url
        results = parse_search_results(html, site, final_url)
        row["search_result_count"] = len(results)
        dated = [
            (result, normalize_date(result.published_date, site))
            for result in results
            if normalize_date(result.published_date, site)
        ]
        row["search_dated_count"] = len(dated)
        if dated:
            result, normalized = dated[0]
            row["search_date_available"] = True
            row["search_date_raw_example"] = result.published_date
            row["search_date_normalized_example"] = normalized
            row["search_article_url_example"] = result.url
            row["search_title_example"] = result.title
        representative = first_article_with_or_without_search_date(results, site)
        if representative:
            row["article_url_example"] = representative.url
            row["article_url_looks_valid"] = looks_like_article_url(representative.url, site)
            if not row["search_title_example"]:
                row["search_title_example"] = representative.title
            try:
                article_response = client.get(representative.url)
                row["article_status"] = article_response.status_code
                article_raw = parse_article_published_date(article_response.text)
                article_normalized = normalize_published_date(
                    article_raw, None, "explicit_year_only"
                )
                row["article_date_raw_example"] = article_raw
                row["article_date_normalized_example"] = article_normalized
                row["article_date_available"] = bool(article_normalized)
            except Exception as exc:  # noqa: BLE001 - audit should continue.
                row["article_error"] = f"{type(exc).__name__}: {exc}"
        if row["search_date_available"]:
            row["judgement"] = "検索結果で取得可能"
        elif row["article_date_available"]:
            row["judgement"] = "検索結果は不可、記事ページで取得可能"
        elif row["search_result_count"]:
            row["judgement"] = "検索結果あり、日付は未確認"
        else:
            row["judgement"] = "検索結果未取得"
    except Exception as exc:  # noqa: BLE001 - audit should continue across all sites.
        row["search_error"] = f"{type(exc).__name__}: {exc}"
        row["judgement"] = "検索結果取得エラー"
    return row


def markdown_link(label: str | None, url: str | None) -> str:
    """Return a compact Markdown link."""

    if not url:
        return ""
    label = (label or url).replace("|", "/").replace("\n", " ")
    if len(label) > 36:
        label = label[:35] + "..."
    return f"[{label}]({url})"


def write_markdown(rows: list[dict[str, Any]]) -> None:
    """Write the audit as a Markdown table."""

    lines = [
        "# 掲載日取得可否 全サイト調査",
        "",
        f"- 調査クエリ: `{QUERY}`",
        "- ①検索結果URL、②検索結果画面の日付取得可否、③記事URL例、④記事ページの日付取得可否を一覧化。",
        "- `検索結果で取得可能` は現行設定の `result_item_selector` / `date_selector` で正規化済み日付を得られた状態。",
        "- `記事ページで取得可能` は共通fallbackの `article:published_time` / JSON-LD `datePublished` / `time[datetime]` 等で取得できた状態。",
        "",
        "| site_id | サイト | ①トヨタ検索URL | ②検索結果の日付 | 検索結果根拠 | ③記事URL例 | ④記事ページの日付 | 記事根拠 | 判定 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        search_date = (
            f"可: `{row['search_date_normalized_example']}`"
            if row["search_date_available"]
            else "不可/未確認"
        )
        search_basis = " / ".join(
            value
            for value in [
                f"`{row['date_selector']}`" if row.get("date_selector") else "`date_selector: null`",
                row.get("search_date_raw_example"),
                f"{row.get('search_dated_count')}/{row.get('search_result_count')}件",
                row.get("fetch_method"),
            ]
            if value
        )
        article_date = (
            f"可: `{row['article_date_normalized_example']}`"
            if row["article_date_available"]
            else "不可/未確認"
        )
        article_basis = " / ".join(
            value
            for value in [
                row.get("article_date_source"),
                row.get("article_date_raw_example"),
                str(row.get("article_status")) if row.get("article_status") else None,
                "記事URL例が疑わしい" if row.get("article_url_example") and not row.get("article_url_looks_valid") else None,
                row.get("article_error"),
            ]
            if value
        )
        lines.append(
            "| {site_id} | {site_name} | {search_url} | {search_date} | {search_basis} | "
            "{article_url} | {article_date} | {article_basis} | {judgement} |".format(
                site_id=row["site_id"],
                site_name=row["site_name"].replace("|", "/"),
                search_url=markdown_link("検索", row["search_url"]),
                search_date=search_date.replace("|", "/"),
                search_basis=search_basis.replace("|", "/").replace("\n", " ")[:160],
                article_url=markdown_link("記事", row.get("article_url_example")),
                article_date=article_date.replace("|", "/"),
                article_basis=article_basis.replace("|", "/").replace("\n", " ")[:160],
                judgement=(row.get("judgement") or "").replace("|", "/"),
            )
        )
    (ROOT / "docs/site_date_availability_matrix.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    sites = [site for site in load_sites(ROOT / "config/sites.yaml") if site.enabled]
    rows = []
    with httpx.Client(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 news-monitor-date-audit/0.1"},
    ) as client:
        for site in sites:
            rows.append(audit_site(client, site))
            time.sleep(0.5)
    work_dir = ROOT / "work"
    work_dir.mkdir(exist_ok=True)
    (work_dir / "site_date_availability_matrix.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(rows)
    print(f"audited {len(rows)} sites")


if __name__ == "__main__":
    main()
