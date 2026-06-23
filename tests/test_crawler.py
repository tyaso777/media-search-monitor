from __future__ import annotations

from dataclasses import replace

from news_monitor import database
from news_monitor.config import load_app_config, load_sites
from news_monitor.crawler import Crawler
from news_monitor.fetcher import FetchResponse


class StaticFixtureFetcher:
    def __init__(self, html: str) -> None:
        self.html = html

    def fetch(self, url, site):
        return FetchResponse(url=url, html=self.html)


class FailingFetcher:
    def fetch(self, url, site):
        if site.site_id == "sample_news":
            raise RuntimeError("boom")
        return FetchResponse(url=url, html="")


class MappingFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def fetch(self, url, site):
        self.urls.append(url)
        if url in self.pages:
            return FetchResponse(url=url, html=self.pages[url])
        return FetchResponse(url=url, html=self.pages["__search__"])


def test_crawl_persists_results_and_skips_playwright_disabled(imported_conn, repo_root, fixture_html):
    app_config = load_app_config(repo_root / "config" / "app.yaml")
    crawler = Crawler(
        imported_conn,
        app_config,
        static_fetcher=StaticFixtureFetcher(fixture_html),
        sleep_enabled=False,
    )

    crawler.crawl()

    assert database.count_rows(imported_conn, "search_result_items") == 2
    assert database.count_rows(imported_conn, "search_result_hits") == 6
    assert database.count_rows(imported_conn, "crawl_skips") == 3
    assert database.count_rows(imported_conn, "fetch_errors") == 0


def test_crawl_records_errors_and_continues(conn, repo_root):
    app_config = load_app_config(repo_root / "config" / "app.yaml")
    keywords = database.enabled_keywords(conn)
    assert keywords == []
    from news_monitor.config import load_keywords

    database.import_keywords(conn, load_keywords(repo_root / "config" / "keywords.csv")[:1])
    sample_site, dynamic_site = load_sites(repo_root / "config" / "sites.yaml")[:2]
    database.import_sites(
        conn,
        [
            replace(sample_site, enabled=True, requires_playwright=False),
            replace(dynamic_site, enabled=True, requires_playwright=False),
        ],
    )

    crawler = Crawler(conn, app_config, static_fetcher=FailingFetcher(), sleep_enabled=False)
    crawler.crawl()

    assert database.count_rows(conn, "fetch_errors") == 1
    assert database.count_rows(conn, "search_runs") == 1


def test_crawl_fills_missing_date_from_article_page(conn, repo_root):
    app_config = load_app_config(repo_root / "config" / "app.yaml")
    from news_monitor.config import load_keywords

    database.import_keywords(conn, load_keywords(repo_root / "config" / "keywords.csv")[:1])
    sample_site = replace(
        load_sites(repo_root / "config" / "sites.yaml")[0],
        enabled=True,
        date_selector=None,
    )
    database.import_sites(conn, [sample_site])
    article_url = "https://example.com/articles/100"
    search_html = """
    <article class="search-result">
      <a class="title" href="https://example.com/articles/100">Article without date</a>
      <p class="snippet">No date here.</p>
    </article>
    """
    article_html = """
    <html>
      <head>
        <meta property="article:published_time" content="2026-06-20T08:30:00+09:00">
      </head>
      <body>Article</body>
    </html>
    """
    fetcher = MappingFetcher({"__search__": search_html, article_url: article_html})

    crawler = Crawler(conn, app_config, static_fetcher=fetcher, sleep_enabled=False)
    crawler.crawl()

    row = conn.execute("SELECT published_date FROM search_result_items").fetchone()
    assert row["published_date"] == "2026/06/20"
    assert article_url in fetcher.urls

