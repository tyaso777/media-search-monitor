"""Crawler orchestration for configured sites and keywords."""

from __future__ import annotations

import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import BoundedSemaphore
from typing import Protocol

from news_monitor import database
from news_monitor.date_utils import best_published_date
from news_monitor.fetcher import (
    FetchResponse,
    GoogleCseFetcher,
    HttpxFetcher,
    PlaywrightFetcher,
    PlaywrightFormFetcher,
)
from news_monitor.models import AppConfig, ParsedResult, SiteConfig
from news_monitor.parser import parse_article_published_date, parse_search_results
from news_monitor.url_utils import encode_query

LOGGER = logging.getLogger(__name__)


class FetcherProtocol(Protocol):
    """Fetcher protocol used by the crawler."""

    def fetch(self, url: str, site: SiteConfig) -> FetchResponse:
        """Fetch a URL for a site."""


APP_TIMEZONE = timezone(timedelta(hours=9))


def utc_now() -> str:
    """Return the current application timestamp as ISO-8601 text."""

    return datetime.now(APP_TIMEZONE).replace(microsecond=0).isoformat()


class Crawler:
    """Run configured site searches and persist results."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        app_config: AppConfig,
        static_fetcher: FetcherProtocol | None = None,
        playwright_fetcher: FetcherProtocol | None = None,
        playwright_form_fetcher: FetcherProtocol | None = None,
        google_cse_fetcher: FetcherProtocol | None = None,
        sleep_enabled: bool = True,
        site_ids: set[str] | None = None,
        candidate_keyword_ids: set[str] | None = None,
        max_sites: int | None = None,
        max_keywords: int | None = None,
    ) -> None:
        """Initialize crawler dependencies."""

        self.conn = conn
        self.app_config = app_config
        self.static_fetcher = static_fetcher or HttpxFetcher(app_config.crawler.request_timeout_seconds)
        self.playwright_fetcher = playwright_fetcher or PlaywrightFetcher(app_config)
        self.playwright_form_fetcher = playwright_form_fetcher or PlaywrightFormFetcher(app_config)
        self.google_cse_fetcher = google_cse_fetcher or GoogleCseFetcher(
            app_config.crawler.request_timeout_seconds
        )
        self.sleep_enabled = sleep_enabled
        self.site_ids = site_ids
        self.candidate_keyword_ids = candidate_keyword_ids
        self.max_sites = max_sites
        self.max_keywords = max_keywords
        self.db_path = database.main_database_path(conn)
        max_playwright = max(1, app_config.crawler.max_concurrent_playwright_sites)
        self.playwright_semaphore = BoundedSemaphore(max_playwright)

    def crawl(self) -> str:
        """Run a full crawl and return the run ID."""

        started_at = utc_now()
        run_id = database.create_run(self.conn, started_at)
        status = "success"
        try:
            sites = self._sites_to_crawl()
            keywords = self._keywords_to_crawl()
            if self._should_run_parallel(sites):
                self._crawl_sites_parallel(run_id, sites, keywords)
            else:
                for site in sites:
                    self._crawl_site(self.conn, run_id, site, keywords)
        except Exception as exc:  # pragma: no cover - defensive final run status
            status = "failed"
            database.record_fetch_error(
                self.conn, run_id, utc_now(), type(exc).__name__, str(exc)
            )
            LOGGER.exception("Unexpected crawl failure")
        finally:
            self.conn.commit()
            database.finish_run(self.conn, run_id, utc_now(), status)
        return run_id

    def _should_run_parallel(self, sites: list[SiteConfig]) -> bool:
        """Return true when this crawl can use site-level concurrency."""

        return (
            self.app_config.crawler.max_concurrent_sites > 1
            and len(sites) > 1
            and self.db_path is not None
        )

    def _crawl_sites_parallel(
        self, run_id: str, sites: list[SiteConfig], keywords: list[sqlite3.Row]
    ) -> None:
        """Crawl multiple sites concurrently while keeping each site sequential."""

        assert self.db_path is not None
        max_workers = min(self.app_config.crawler.max_concurrent_sites, len(sites))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._crawl_site_with_new_connection, run_id, site, keywords, self.db_path)
                for site in sites
            ]
            for future in as_completed(futures):
                future.result()

    def _crawl_site_with_new_connection(
        self, run_id: str, site: SiteConfig, keywords: list[sqlite3.Row], db_path: Path
    ) -> None:
        """Open a worker connection and crawl one site."""

        with database.connect(db_path, self.app_config.crawler.db_busy_timeout_seconds) as conn:
            self._crawl_site(conn, run_id, site, keywords)

    def _crawl_site(
        self, conn: sqlite3.Connection, run_id: str, site: SiteConfig, keywords: list[sqlite3.Row]
    ) -> None:
        """Crawl one site for all enabled candidate keywords."""

        article_date_lookups = 0
        article_date_cache: dict[str, str | None] = {}
        for keyword in keywords:
            if self._requires_playwright_runtime(site) and not self.app_config.playwright.enabled:
                self._write_with_retry(
                    conn,
                    lambda: self._record_skip(conn, run_id, site, keyword),
                )
                continue
            query = encode_query(keyword["candidate_keyword"], site.query_encoding)
            page_url = site.search_url_template.format(query=query)
            try:
                fetcher = self._fetcher_for_site(site)
                if self._requires_playwright_runtime(site):
                    with self.playwright_semaphore:
                        fetched = fetcher.fetch(page_url, site)
                else:
                    fetched = fetcher.fetch(page_url, site)
                fetched_at = utc_now()
                results = self._filter_results(
                    self._normalize_result_dates(
                        parse_search_results(fetched.html, site, fetched.url),
                        site,
                        fetched_at,
                    ),
                    site,
                    keyword["candidate_keyword"],
                )
                results, article_date_lookups = self._fill_missing_dates_from_articles(
                    conn,
                    run_id,
                    site,
                    keyword,
                    results,
                    fetched_at,
                    article_date_lookups,
                    article_date_cache,
                )
                self._write_with_retry(
                    conn,
                    lambda: self._persist_results(
                        conn, run_id, site, keyword, fetched.url, fetched_at, results
                    ),
                )
            except Exception as exc:
                self._write_with_retry(
                    conn,
                    lambda: self._record_fetch_error(
                        conn, run_id, site, keyword, page_url, exc
                    ),
                )
                LOGGER.warning("Failed to crawl %s for %s: %s", site.site_id, query, exc)
            if self.sleep_enabled and site.rate_limit_seconds > 0:
                time.sleep(site.rate_limit_seconds)

    def _requires_playwright_runtime(self, site: SiteConfig) -> bool:
        """Return whether the configured fetch strategy needs Playwright enabled."""

        return site.fetch_strategy in {"playwright", "playwright_form"}

    def _fetcher_for_site(self, site: SiteConfig) -> FetcherProtocol:
        """Return the fetcher selected by the site's fetch strategy."""

        if site.fetch_strategy == "httpx":
            return self.static_fetcher
        if site.fetch_strategy == "playwright":
            return self.playwright_fetcher
        if site.fetch_strategy == "playwright_form":
            return self.playwright_form_fetcher
        if site.fetch_strategy == "google_cse":
            return self.google_cse_fetcher
        raise ValueError(f"Unsupported fetch_strategy: {site.fetch_strategy}")

    def _fill_missing_dates_from_articles(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        site: SiteConfig,
        keyword: sqlite3.Row,
        results: list[ParsedResult],
        fetched_at: str,
        article_date_lookups: int,
        article_date_cache: dict[str, str | None],
    ) -> tuple[list[ParsedResult], int]:
        """Fetch article pages for results whose published date is still unknown."""

        if not self.app_config.crawler.article_date_lookup_enabled:
            return results, article_date_lookups
        limit = self.app_config.crawler.article_date_lookup_max_per_site
        if limit <= 0 or article_date_lookups >= limit:
            return results, article_date_lookups

        filled: list[ParsedResult] = []
        for result in results:
            if result.published_date:
                filled.append(result)
                continue
            if result.url in article_date_cache:
                cached_date = article_date_cache[result.url]
                filled.append(
                    replace(result, published_date=cached_date) if cached_date else result
                )
                continue
            if article_date_lookups >= limit:
                filled.append(result)
                continue
            try:
                fetched = self.static_fetcher.fetch(result.url, site)
                article_date_lookups += 1
                article_date = parse_article_published_date(fetched.html)
                published_date = best_published_date(
                    article_date,
                    None,
                    None,
                    fetched_at,
                    "explicit_year_only",
                    fetched.url,
                )
                article_date_cache[result.url] = published_date
                if published_date:
                    filled.append(replace(result, published_date=published_date))
                else:
                    filled.append(result)
            except Exception as exc:
                article_date_lookups += 1
                article_date_cache[result.url] = None
                self._write_with_retry(
                    conn,
                    lambda exc=exc, result=result: self._record_fetch_error(
                        conn,
                        run_id,
                        site,
                        keyword,
                        result.url,
                        exc,
                    ),
                )
                filled.append(result)
            if (
                self.sleep_enabled
                and self.app_config.crawler.article_date_lookup_rate_limit_seconds > 0
            ):
                time.sleep(self.app_config.crawler.article_date_lookup_rate_limit_seconds)
        return filled, article_date_lookups

    def _write_with_retry(self, conn: sqlite3.Connection, operation) -> None:
        """Run one short write transaction with SQLite lock retry."""

        database.run_with_lock_retry(
            conn,
            operation,
            self.app_config.crawler.db_write_retries,
            self.app_config.crawler.db_write_retry_delay_seconds,
        )

    def _persist_results(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        site: SiteConfig,
        keyword: sqlite3.Row,
        fetched_url: str,
        fetched_at: str,
        results,
    ) -> None:
        """Persist parsed results for one fetched search page."""

        for result in results:
            result_item_id = database.upsert_result(conn, site, result, fetched_url, fetched_at)
            database.upsert_hit(conn, result_item_id, keyword, site.site_id, run_id, fetched_at)
        conn.commit()

    def _filter_results(
        self, results: list[ParsedResult], site: SiteConfig, candidate_keyword: str
    ) -> list[ParsedResult]:
        """Apply optional site-level result filters after parsing."""

        if not site.require_keyword_in_result:
            return results
        needle = candidate_keyword.casefold()
        filtered: list[ParsedResult] = []
        for result in results:
            haystack = " ".join(
                value or ""
                for value in [result.title, result.snippet, result.published_date, result.url]
            ).casefold()
            if needle in haystack:
                filtered.append(result)
        return filtered

    def _normalize_result_dates(
        self, results: list[ParsedResult], site: SiteConfig, fetched_at: str
    ) -> list[ParsedResult]:
        """Normalize result published dates before persistence."""

        normalized: list[ParsedResult] = []
        for result in results:
            published_date = best_published_date(
                result.published_date,
                result.title,
                result.snippet,
                fetched_at,
                site.date_rule,
                result.url,
            )
            normalized.append(replace(result, published_date=published_date))
        return normalized

    def _record_fetch_error(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        site: SiteConfig,
        keyword: sqlite3.Row,
        page_url: str,
        exc: Exception,
    ) -> None:
        """Persist one fetch error and commit it."""

        database.record_fetch_error(
            conn,
            run_id,
            utc_now(),
            type(exc).__name__,
            str(exc),
            site.site_id,
            keyword,
            page_url,
        )
        conn.commit()

    def _record_skip(
        self, conn: sqlite3.Connection, run_id: str, site: SiteConfig, keyword: sqlite3.Row
    ) -> None:
        """Persist one crawl skip and commit it."""

        database.record_skip(
            conn,
            run_id,
            utc_now(),
            "playwright_disabled",
            site.site_id,
            keyword,
        )
        conn.commit()

    def _sites_to_crawl(self) -> list[SiteConfig]:
        """Return enabled sites after optional CLI filtering."""

        sites = database.enabled_sites(self.conn)
        if self.site_ids is not None:
            sites = [site for site in sites if site.site_id in self.site_ids]
        if self.max_sites is not None:
            sites = sites[: self.max_sites]
        return sites

    def _keywords_to_crawl(self) -> list[sqlite3.Row]:
        """Return enabled candidate keywords after optional CLI filtering."""

        keywords = database.enabled_keywords(self.conn)
        if self.candidate_keyword_ids is not None:
            keywords = [
                keyword
                for keyword in keywords
                if keyword["candidate_keyword_id"] in self.candidate_keyword_ids
            ]
        if self.max_keywords is not None:
            keywords = keywords[: self.max_keywords]
        return keywords
