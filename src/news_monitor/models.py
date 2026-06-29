"""Typed models for news monitor configuration and parsed results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaywrightConfig:
    """Global Playwright runtime settings."""

    enabled: bool
    headless: bool
    timeout_seconds: int


@dataclass(frozen=True)
class CrawlerConfig:
    """Global crawler runtime settings."""

    default_rate_limit_seconds: int
    request_timeout_seconds: int
    max_retries: int
    max_concurrent_sites: int
    max_concurrent_playwright_sites: int
    db_busy_timeout_seconds: int
    db_write_retries: int
    db_write_retry_delay_seconds: float
    article_date_lookup_enabled: bool
    article_date_lookup_max_per_site: int
    article_date_lookup_rate_limit_seconds: float
    structure_check_enabled: bool
    structure_check_interval_hours: int
    structure_check_keyword: str
    structure_check_min_results: int
    structure_check_min_baseline_checks: int
    structure_check_result_count_drop_ratio: float
    structure_check_title_match_rate_drop_points: float
    structure_check_title_match_warning_rate: float


@dataclass(frozen=True)
class ReportConfig:
    """HTML report output settings."""

    output_dir: str


@dataclass(frozen=True)
class AppConfig:
    """Application-level settings."""

    playwright: PlaywrightConfig
    crawler: CrawlerConfig
    report: ReportConfig


@dataclass(frozen=True)
class SiteConfig:
    """Search result page configuration for one site."""

    site_id: str
    site_name: str
    enabled: bool
    search_url_template: str
    query_encoding: str
    requires_playwright: bool
    result_item_selector: str
    title_selector: str | None
    url_selector: str | None
    date_selector: str | None
    snippet_selector: str | None
    rate_limit_seconds: int
    user_agent: str
    max_pages: int
    next_page_selector: str | None
    result_container_selector: str | None = None
    no_results_text: str | None = None
    notes: str | None = None
    url_include_patterns: tuple[str, ...] = ()
    url_exclude_patterns: tuple[str, ...] = ()
    require_keyword_in_result: bool = False
    fetch_strategy: str = "httpx"
    parser_strategy: str = "css_selectors"
    date_strategy: str = "css_selector"
    date_rule: str = "explicit_year_only"
    google_cse_lightweight_candidate: bool = False
    google_cse_cx: str | None = None
    google_cse_sort: str | None = None
    google_cse_notes: str | None = None
    form_input_selector: str | None = None
    form_submit_selector: str | None = None
    form_submit_index: int = -1


@dataclass(frozen=True)
class KeywordCandidate:
    """Candidate keyword used for actual search queries."""

    base_keyword_id: str
    base_keyword: str
    group_type: str
    candidate_keyword_id: str
    candidate_keyword: str
    enabled: bool
    notes: str | None
    source_base_keyword_id: str | None = None
    source_candidate_keyword_id: str | None = None


@dataclass(frozen=True)
class ParsedResult:
    """Search result item extracted from a result page."""

    title: str | None
    url: str
    published_date: str | None
    snippet: str | None
