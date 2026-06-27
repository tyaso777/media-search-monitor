from __future__ import annotations

from dataclasses import replace
import threading
import time

import httpx

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


class StatusFailingFetcher:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def fetch(self, url, site):
        request = httpx.Request("GET", url)
        response = httpx.Response(self.status_code, request=request, text="blocked")
        raise httpx.HTTPStatusError("blocked", request=request, response=response)


class MappingFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def fetch(self, url, site):
        self.urls.append(url)
        if url in self.pages:
            return FetchResponse(url=url, html=self.pages[url])
        return FetchResponse(url=url, html=self.pages["__search__"])


class ConcurrencyTrackingFetcher:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.calls: list[str] = []
        self.started_at: list[float] = []

    def fetch(self, url, site):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.calls.append(site.site_id)
            self.started_at.append(time.monotonic())
        time.sleep(0.05)
        with self.lock:
            self.active -= 1
        return FetchResponse(url=url, html="<!doctype html><html><body></body></html>")


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


def test_crawl_backs_off_site_after_403(conn, repo_root, fixture_html):
    app_config = load_app_config(repo_root / "config" / "app.yaml")
    from news_monitor.config import load_keywords

    database.import_keywords(conn, load_keywords(repo_root / "config" / "keywords.csv")[:3])
    sample_site = replace(
        load_sites(repo_root / "config" / "sites.yaml")[0],
        enabled=True,
        requires_playwright=False,
    )
    database.import_sites(conn, [sample_site])

    crawler = Crawler(
        conn,
        app_config,
        static_fetcher=StatusFailingFetcher(403),
        sleep_enabled=False,
    )
    crawler.crawl()

    assert database.count_rows(conn, "fetch_errors") == 1
    assert database.count_rows(conn, "crawl_skips") == 2
    backoff = conn.execute("SELECT * FROM site_crawl_backoff WHERE site_id = 'sample_news'").fetchone()
    assert backoff["status_code"] == 403
    assert backoff["failure_count"] == 1
    assert backoff["backoff_until"]
    skip_reasons = [
        row["reason"] for row in conn.execute("SELECT reason FROM crawl_skips ORDER BY created_at")
    ]
    assert skip_reasons == ["site_backoff_403", "site_backoff_403"]

    retry_crawler = Crawler(
        conn,
        app_config,
        static_fetcher=StaticFixtureFetcher(fixture_html),
        sleep_enabled=False,
    )
    retry_crawler.crawl()

    assert database.count_rows(conn, "search_result_items") == 0
    assert database.count_rows(conn, "fetch_errors") == 1
    assert database.count_rows(conn, "crawl_skips") == 5


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


def test_google_cse_sites_are_prioritized(conn, repo_root):
    app_config = load_app_config(repo_root / "config" / "app.yaml")
    sample_site, dynamic_site = load_sites(repo_root / "config" / "sites.yaml")[:2]
    http_site = replace(
        sample_site,
        site_id="ordinary_site",
        enabled=True,
        requires_playwright=False,
        fetch_strategy="httpx",
    )
    cse_site = replace(
        dynamic_site,
        site_id="cse_site",
        enabled=True,
        requires_playwright=False,
        fetch_strategy="google_cse",
        google_cse_cx="test-cx",
    )
    database.import_sites(conn, [http_site, cse_site])

    crawler = Crawler(conn, app_config, sleep_enabled=False)

    assert [site.site_id for site in crawler._sites_to_crawl()] == [
        "cse_site",
        "ordinary_site",
    ]


def test_google_cse_fetches_are_globally_serialized(conn, repo_root):
    app_config = load_app_config(repo_root / "config" / "app.yaml")
    app_config = replace(
        app_config,
        crawler=replace(app_config.crawler, max_concurrent_sites=2),
    )
    from news_monitor.config import load_keywords

    database.import_keywords(conn, load_keywords(repo_root / "config" / "keywords.csv")[:1])
    base_site = load_sites(repo_root / "config" / "sites.yaml")[0]
    cse_sites = [
        replace(
            base_site,
            site_id=f"cse_site_{index}",
            site_name=f"CSE Site {index}",
            enabled=True,
            requires_playwright=False,
            fetch_strategy="google_cse",
            google_cse_cx=f"test-cx-{index}",
        )
        for index in range(2)
    ]
    database.import_sites(conn, cse_sites)
    fetcher = ConcurrencyTrackingFetcher()

    crawler = Crawler(
        conn,
        app_config,
        google_cse_fetcher=fetcher,
        sleep_enabled=False,
    )
    crawler.crawl()

    assert sorted(fetcher.calls) == ["cse_site_0", "cse_site_1"]
    assert fetcher.max_active == 1


def test_google_cse_fetches_wait_between_requests(conn, repo_root):
    app_config = load_app_config(repo_root / "config" / "app.yaml")
    app_config = replace(
        app_config,
        crawler=replace(app_config.crawler, max_concurrent_sites=2),
    )
    from news_monitor.config import load_keywords

    database.import_keywords(conn, load_keywords(repo_root / "config" / "keywords.csv")[:1])
    base_site = load_sites(repo_root / "config" / "sites.yaml")[0]
    cse_sites = [
        replace(
            base_site,
            site_id=f"cse_wait_site_{index}",
            site_name=f"CSE Wait Site {index}",
            enabled=True,
            requires_playwright=False,
            fetch_strategy="google_cse",
            google_cse_cx=f"test-cx-{index}",
        )
        for index in range(2)
    ]
    database.import_sites(conn, cse_sites)
    fetcher = ConcurrencyTrackingFetcher()

    crawler = Crawler(
        conn,
        app_config,
        google_cse_fetcher=fetcher,
        sleep_enabled=True,
    )
    crawler.google_cse_min_interval_seconds = 0.05
    crawler.crawl()

    assert len(fetcher.started_at) == 2
    assert fetcher.started_at[1] - fetcher.started_at[0] >= 0.045
