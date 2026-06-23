"""Configuration file loading utilities."""

from __future__ import annotations

import csv
import re
import uuid
from pathlib import Path
from typing import Any

import yaml

from news_monitor.models import (
    AppConfig,
    CrawlerConfig,
    KeywordCandidate,
    PlaywrightConfig,
    ReportConfig,
    SiteConfig,
)

KEYWORD_NAMESPACE = uuid.UUID("1d78b9f1-0ef5-46f7-8f2f-4f54aefdc490")
LEGACY_BASE_ID_RE = re.compile(r"^b\d+$")
LEGACY_CANDIDATE_ID_RE = re.compile(r"^c\d+$")


def _as_bool(value: Any) -> bool:
    """Convert common configuration values to bool."""

    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_group_type(value: str | None) -> str:
    """Return the supported keyword group type."""

    normalized = (value or "company").strip().lower()
    return normalized if normalized in {"company", "topic"} else "company"


def keyword_group_id(
    base_keyword: str, configured_id: str | None = None, group_type: str = "company"
) -> str:
    """Return the stable internal ID for a base keyword."""

    configured_id = (configured_id or "").strip()
    if configured_id and not LEGACY_BASE_ID_RE.fullmatch(configured_id):
        return configured_id
    group_type = normalize_group_type(group_type)
    namespace_key = (
        f"keyword-group:{base_keyword}"
        if group_type == "company"
        else f"keyword-group:{group_type}:{base_keyword}"
    )
    digest = uuid.uuid5(KEYWORD_NAMESPACE, namespace_key).hex[:12]
    return f"kwg_{digest}"


def keyword_candidate_id(
    base_keyword: str,
    candidate_keyword: str,
    configured_id: str | None = None,
    group_type: str = "company",
) -> str:
    """Return the stable internal ID for a candidate keyword."""

    configured_id = (configured_id or "").strip()
    if configured_id and not LEGACY_CANDIDATE_ID_RE.fullmatch(configured_id):
        return configured_id
    group_type = normalize_group_type(group_type)
    namespace_key = (
        f"keyword-candidate:{base_keyword}\0{candidate_keyword}"
        if group_type == "company"
        else f"keyword-candidate:{group_type}\0{base_keyword}\0{candidate_keyword}"
    )
    digest = uuid.uuid5(
        KEYWORD_NAMESPACE, namespace_key
    ).hex[:12]
    return f"kwc_{digest}"


def load_app_config(path: Path) -> AppConfig:
    """Load app-level YAML configuration.

    Args:
        path: Path to app.yaml.

    Returns:
        Parsed application configuration.
    """

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    playwright = raw.get("playwright", {})
    crawler = raw.get("crawler", {})
    report = raw.get("report", {})
    return AppConfig(
        playwright=PlaywrightConfig(
            enabled=_as_bool(playwright.get("enabled", False)),
            headless=_as_bool(playwright.get("headless", True)),
            timeout_seconds=int(playwright.get("timeout_seconds", 30)),
        ),
        crawler=CrawlerConfig(
            default_rate_limit_seconds=int(crawler.get("default_rate_limit_seconds", 3)),
            request_timeout_seconds=int(crawler.get("request_timeout_seconds", 30)),
            max_retries=int(crawler.get("max_retries", 2)),
            max_concurrent_sites=int(crawler.get("max_concurrent_sites", 1)),
            max_concurrent_playwright_sites=int(crawler.get("max_concurrent_playwright_sites", 1)),
            db_busy_timeout_seconds=int(crawler.get("db_busy_timeout_seconds", 30)),
            db_write_retries=int(crawler.get("db_write_retries", 5)),
            db_write_retry_delay_seconds=float(crawler.get("db_write_retry_delay_seconds", 0.25)),
            article_date_lookup_enabled=_as_bool(
                crawler.get("article_date_lookup_enabled", True)
            ),
            article_date_lookup_max_per_site=int(
                crawler.get("article_date_lookup_max_per_site", 30)
            ),
            article_date_lookup_rate_limit_seconds=float(
                crawler.get("article_date_lookup_rate_limit_seconds", 1.0)
            ),
        ),
        report=ReportConfig(output_dir=str(report.get("output_dir", "reports"))),
    )


def load_sites(path: Path) -> list[SiteConfig]:
    """Load site definitions from YAML.

    Args:
        path: Path to sites.yaml.

    Returns:
        Site definitions.
    """

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides = _load_site_overrides(path.parent / "site_overrides.yaml")
    date_rules = _load_site_date_rules(path.parent / "date_rules.yaml")
    sites: list[SiteConfig] = []
    for item in raw.get("sites", []):
        site_id = str(item["site_id"])
        item = {**item, **overrides.get(site_id, {}), **date_rules.get(site_id, {})}
        sites.append(
            SiteConfig(
                site_id=site_id,
                site_name=str(item["site_name"]),
                enabled=_as_bool(item.get("enabled", True)),
                search_url_template=str(item["search_url_template"]),
                query_encoding=str(item.get("query_encoding", "utf-8")),
                requires_playwright=_as_bool(item.get("requires_playwright", False)),
                result_item_selector=str(item["result_item_selector"]),
                title_selector=item.get("title_selector"),
                url_selector=item.get("url_selector"),
                date_selector=item.get("date_selector"),
                snippet_selector=item.get("snippet_selector"),
                rate_limit_seconds=int(item.get("rate_limit_seconds", 3)),
                user_agent=str(item.get("user_agent", "news-monitor-bot/0.1")),
                max_pages=int(item.get("max_pages", 1)),
                next_page_selector=item.get("next_page_selector"),
                result_container_selector=item.get("result_container_selector"),
                no_results_text=item.get("no_results_text"),
                notes=item.get("notes"),
                url_include_patterns=tuple(item.get("url_include_patterns", []) or ()),
                url_exclude_patterns=tuple(item.get("url_exclude_patterns", []) or ()),
                require_keyword_in_result=_as_bool(item.get("require_keyword_in_result", False)),
                fetch_strategy=str(item.get("fetch_strategy", _default_fetch_strategy(item))),
                parser_strategy=str(item.get("parser_strategy", "css_selectors")),
                date_strategy=str(item.get("date_strategy", _default_date_strategy(item))),
                date_rule=str(item.get("date_rule", "explicit_year_only")),
                google_cse_lightweight_candidate=_as_bool(
                    item.get("google_cse_lightweight_candidate", False)
                ),
                google_cse_cx=item.get("google_cse_cx"),
                google_cse_sort=item.get("google_cse_sort"),
                google_cse_notes=item.get("google_cse_notes"),
                form_input_selector=item.get("form_input_selector"),
                form_submit_selector=item.get("form_submit_selector"),
                form_submit_index=int(item.get("form_submit_index", -1)),
            )
        )
    return sites


def _default_fetch_strategy(item: dict[str, Any]) -> str:
    """Return the default search-page fetch strategy for one site."""

    if _as_bool(item.get("requires_playwright", False)):
        return "playwright"
    return "httpx"


def _default_date_strategy(item: dict[str, Any]) -> str:
    """Return the default published-date extraction strategy for one site."""

    if not item.get("date_selector") or item.get("date_rule") == "none":
        return "none"
    return "css_selector"


def _load_site_overrides(path: Path) -> dict[str, dict[str, Any]]:
    """Load optional per-site selector overrides."""

    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(item["site_id"]): item for item in raw.get("overrides", [])}


def _load_site_date_rules(path: Path) -> dict[str, dict[str, Any]]:
    """Load optional per-site published-date normalization rules."""

    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        str(item["site_id"]): {"date_rule": str(item["date_rule"])}
        for item in raw.get("rules", [])
    }


def load_keywords(path: Path) -> list[KeywordCandidate]:
    """Load candidate keywords from CSV.

    Args:
        path: Path to keywords.csv.

    Returns:
        Candidate keyword rows.
    """

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        keywords: list[KeywordCandidate] = []
        for row in reader:
            source_base_keyword_id = row.get("base_keyword_id", "").strip()
            source_candidate_keyword_id = row.get("candidate_keyword_id", "").strip()
            base_keyword = row["base_keyword"]
            candidate_keyword = row["candidate_keyword"]
            group_type = normalize_group_type(row.get("group_type"))
            keywords.append(
                KeywordCandidate(
                    base_keyword_id=keyword_group_id(base_keyword, source_base_keyword_id, group_type),
                    base_keyword=base_keyword,
                    group_type=group_type,
                    candidate_keyword_id=keyword_candidate_id(
                        base_keyword, candidate_keyword, source_candidate_keyword_id, group_type
                    ),
                    candidate_keyword=candidate_keyword,
                    enabled=_as_bool(row.get("enabled", "1")),
                    notes=row.get("notes") or None,
                    source_base_keyword_id=source_base_keyword_id or None,
                    source_candidate_keyword_id=source_candidate_keyword_id or None,
                )
            )
        return keywords
