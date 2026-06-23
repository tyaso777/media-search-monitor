"""CSS selector based parser for search result pages."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Callable

from bs4 import BeautifulSoup, Tag

from news_monitor.models import ParsedResult, SiteConfig
from news_monitor.url_utils import absolute_url

SUPPORTED_PARSER_STRATEGIES = {"css_selectors", "site_specific"}
SUPPORTED_DATE_STRATEGIES = {
    "css_selector",
    "article_page_fallback",
    "title_trailing_date",
    "site_specific",
    "none",
}

SiteSpecificParser = Callable[[str, SiteConfig, str], list[ParsedResult]]
SITE_SPECIFIC_SEARCH_PARSERS: dict[str, SiteSpecificParser] = {}

ARTICLE_DATE_META_SELECTORS = [
    "meta[property='article:published_time']",
    "meta[property='og:published_time']",
    "meta[name='pubdate']",
    "meta[name='publishdate']",
    "meta[name='publish_date']",
    "meta[name='date']",
    "meta[itemprop='datePublished']",
]

ARTICLE_DATE_SELECTORS = [
    "time[datetime]",
    "[itemprop='datePublished']",
    ".published time",
    ".date time",
]


def _selected_text(block: Tag, selector: str | None) -> str | None:
    """Extract stripped text for a selector."""

    if not selector:
        return None
    for found in block.select(selector):
        text = found.get_text(" ", strip=True)
        if text:
            return text
    return None


def _selected_date_text(block: Tag, selector: str | None) -> str | None:
    """Extract date text, preferring machine-readable attributes."""

    if not selector:
        return None
    for found in block.select(selector):
        for attr in ("datetime", "content", "data-date", "data-published"):
            value = found.get(attr)
            if value:
                return str(value).strip()
        text = found.get_text(" ", strip=True)
        if text:
            return text
    return None


def _selected_link(
    block: Tag, selector: str | None, site: SiteConfig, page_url: str
) -> Tag | None:
    """Find the link element for a result block."""

    if block.name == "a":
        return block
    if selector:
        candidates: list[Tag] = []
        for found in block.select(selector):
            if not isinstance(found, Tag):
                continue
            if found.name == "a":
                candidates.append(found)
            else:
                candidates.extend(
                    nested for nested in found.select("a[href]") if isinstance(nested, Tag)
                )
        preferred = _preferred_allowed_link(candidates, site, page_url)
        if preferred:
            return preferred
    return _preferred_allowed_link(block.select("a[href]"), site, page_url)


def _url_allowed(url: str, site: SiteConfig) -> bool:
    """Return whether a URL passes site-level include/exclude filters."""

    if site.url_include_patterns and not any(
        pattern in url for pattern in site.url_include_patterns
    ):
        return False
    if site.url_exclude_patterns and any(pattern in url for pattern in site.url_exclude_patterns):
        return False
    return True


def parse_search_results(html: str, site: SiteConfig, page_url: str) -> list[ParsedResult]:
    """Parse search result items using the site's configured parser strategy."""

    if site.parser_strategy == "css_selectors":
        return _parse_search_results_css_selectors(html, site, page_url)
    if site.parser_strategy == "site_specific":
        parser = SITE_SPECIFIC_SEARCH_PARSERS.get(site.site_id)
        if parser is None:
            raise NotImplementedError(
                f"Site-specific parser is not implemented for site_id={site.site_id}"
            )
        return parser(html, site, page_url)
    raise ValueError(f"Unsupported parser_strategy: {site.parser_strategy}")


def _parse_search_results_css_selectors(
    html: str, site: SiteConfig, page_url: str
) -> list[ParsedResult]:
    """Parse search result items from HTML.

    Args:
        html: Search result page HTML.
        site: Site selector configuration.
        page_url: URL of the search result page, used for relative URLs.

    Returns:
        Parsed result items. Items without URL are skipped.
    """

    soup = BeautifulSoup(html, "html.parser")
    if site.no_results_text and site.no_results_text in soup.get_text(" ", strip=True):
        return []
    results: list[ParsedResult] = []
    roots = soup.select(site.result_container_selector) if site.result_container_selector else [soup]
    for root in roots:
        for block in root.select(site.result_item_selector):
            link = _selected_link(block, site.url_selector, site, page_url)
            href = link.get("href") if link else None
            if not href:
                continue
            result_url = absolute_url(str(href), page_url)
            if not _url_allowed(result_url, site):
                link = _first_allowed_link(block, site, page_url)
                href = link.get("href") if link else None
                if not href:
                    continue
                result_url = absolute_url(str(href), page_url)
            title = _selected_text(block, site.title_selector)
            if title is None and link:
                title = link.get_text(" ", strip=True) or None
            results.append(
                ParsedResult(
                    title=title,
                    url=result_url,
                    published_date=_selected_date_text(block, site.date_selector),
                    snippet=_selected_text(block, site.snippet_selector),
                )
            )
    return results


def parse_article_published_date(html: str) -> str | None:
    """Extract a published date candidate from an article detail page."""

    soup = BeautifulSoup(html, "html.parser")
    json_ld_date = _json_ld_published_date(soup)
    if json_ld_date:
        return json_ld_date
    for selector in ARTICLE_DATE_META_SELECTORS:
        found = soup.select_one(selector)
        if not isinstance(found, Tag):
            continue
        value = found.get("content")
        if value:
            return str(value).strip()
    for selector in ARTICLE_DATE_SELECTORS:
        found = soup.select_one(selector)
        if not isinstance(found, Tag):
            continue
        for attr in ("datetime", "content", "data-date", "data-published"):
            value = found.get(attr)
            if value:
                return str(value).strip()
        text = found.get_text(" ", strip=True)
        if text:
            return text
    return None


def _json_ld_published_date(soup: BeautifulSoup) -> str | None:
    """Extract datePublished from JSON-LD blocks."""

    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        value = _find_json_key(data, ("datePublished", "dateCreated"))
        if value:
            return value
    return None


def _find_json_key(data, keys: Iterable[str]) -> str | None:
    """Recursively find the first string value for one of the given JSON keys."""

    key_set = set(keys)
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key, value in data.items():
            if key in key_set:
                continue
            found = _find_json_key(value, keys)
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_json_key(value, keys)
            if found:
                return found
    return None


def _first_allowed_link(block: Tag, site: SiteConfig, page_url: str) -> Tag | None:
    """Find the first anchor in a block that passes URL filters."""

    if block.name == "a":
        href = block.get("href")
        if href and _url_allowed(absolute_url(str(href), page_url), site):
            return block
        return None
    for anchor in block.select("a[href]"):
        href = anchor.get("href")
        if href and _url_allowed(absolute_url(str(href), page_url), site):
            return anchor
    return None


def _preferred_allowed_link(
    anchors: list[Tag] | list, site: SiteConfig, page_url: str
) -> Tag | None:
    """Prefer allowed links that carry visible text over image-only wrappers."""

    allowed: list[Tag] = []
    for anchor in anchors:
        href = anchor.get("href")
        if href and _url_allowed(absolute_url(str(href), page_url), site):
            allowed.append(anchor)
    if not allowed:
        return None
    for anchor in allowed:
        if anchor.get_text(" ", strip=True):
            return anchor
    return allowed[0]
