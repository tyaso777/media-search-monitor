"""HTML fetchers for static and JavaScript-rendered pages."""

from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from news_monitor.errors import PlaywrightUnavailableError
from news_monitor.models import AppConfig, SiteConfig

LOGGER = logging.getLogger(__name__)

SUPPORTED_FETCH_STRATEGIES = {"httpx", "playwright", "playwright_form", "google_cse"}


@dataclass(frozen=True)
class FetchResponse:
    """Fetched HTML and final URL metadata."""

    url: str
    html: str


class HttpxFetcher:
    """Fetch static HTML pages with httpx."""

    def __init__(self, timeout_seconds: int) -> None:
        """Initialize the fetcher."""

        self.timeout_seconds = timeout_seconds

    def fetch(self, url: str, site: SiteConfig) -> FetchResponse:
        """Fetch a URL with site-specific headers."""

        LOGGER.info("Fetching %s via httpx", url)
        with httpx.Client(
            timeout=self.timeout_seconds,
            headers={"User-Agent": site.user_agent},
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return FetchResponse(url=str(response.url), html=response.text)


class PlaywrightFetcher:
    """Fetch JavaScript-rendered pages when Playwright is installed."""

    def __init__(self, app_config: AppConfig) -> None:
        """Initialize the fetcher from app settings."""

        self.app_config = app_config

    def fetch(self, url: str, site: SiteConfig) -> FetchResponse:
        """Fetch a URL using Playwright.

        Raises:
            PlaywrightUnavailableError: If the optional Playwright dependency is absent.
        """

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise PlaywrightUnavailableError("Playwright is not installed") from exc

        timeout_ms = self.app_config.playwright.timeout_seconds * 1000
        LOGGER.info("Fetching %s via Playwright", url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.app_config.playwright.headless)
            page = browser.new_page(user_agent=site.user_agent)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(3000)
            html = page.content()
            final_url = page.url
            browser.close()
            return FetchResponse(url=final_url, html=html)


class PlaywrightFormFetcher:
    """Submit a JavaScript-rendered search form with Playwright."""

    def __init__(self, app_config: AppConfig) -> None:
        """Initialize the fetcher from app settings."""

        self.app_config = app_config

    def fetch(self, url: str, site: SiteConfig) -> FetchResponse:
        """Open a page, fill the configured search form, and return rendered HTML."""

        if not site.form_input_selector or not site.form_submit_selector:
            raise ValueError(
                f"form_input_selector and form_submit_selector are required for {site.site_id}"
            )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise PlaywrightUnavailableError("Playwright is not installed") from exc

        timeout_ms = self.app_config.playwright.timeout_seconds * 1000
        query = _query_from_search_url(url)
        LOGGER.info("Fetching %s via Playwright form", url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.app_config.playwright.headless)
            page = browser.new_page(user_agent=site.user_agent)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.fill(site.form_input_selector, query, timeout=timeout_ms)
            submit = page.locator(site.form_submit_selector)
            if site.form_submit_index < 0:
                submit.last.click(timeout=timeout_ms)
            else:
                submit.nth(site.form_submit_index).click(timeout=timeout_ms)
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
            page.wait_for_timeout(3000)
            html = page.content()
            final_url = page.url
            browser.close()
            return FetchResponse(url=final_url, html=html)


class GoogleCseFetcher:
    """Placeholder for direct Google CSE result fetching.

    The public CSE widget renders results by first loading cse.js, then calling
    Google's element/v1 JSONP endpoint with the short-lived cse_token from cse.js.
    This fetcher performs the same two HTTP requests and converts the JSONP result
    into the CSE DOM shape already understood by the CSS parser.
    """

    CALLBACK = "google.search.cse.api00000"

    def __init__(self, timeout_seconds: int) -> None:
        """Initialize the fetcher."""

        self.timeout_seconds = timeout_seconds

    def fetch(self, url: str, site: SiteConfig) -> FetchResponse:
        """Fetch Google CSE results directly and return synthetic result HTML."""

        if not site.google_cse_cx:
            raise ValueError(f"google_cse_cx is required for site_id={site.site_id}")
        query = _query_from_search_url(url)
        headers = {"User-Agent": site.user_agent, "Referer": url}
        with httpx.Client(timeout=self.timeout_seconds, headers=headers, follow_redirects=True) as client:
            cse_config = _fetch_cse_config(client, site.google_cse_cx)
            response = client.get(_google_cse_element_url(site, cse_config, query, url))
            response.raise_for_status()
            payload = _parse_google_cse_jsonp(response.text, self.CALLBACK)
            _raise_for_google_cse_error(payload, response.request)
        return FetchResponse(url=url, html=_google_cse_payload_to_html(payload))


def _query_from_search_url(url: str) -> str:
    """Extract the search query from a site search URL."""

    params = parse_qs(urlparse(url).query)
    for key in ("q", "keyword", "KEYWORD", "kw", "fulltext"):
        values = params.get(key)
        if values and values[0]:
            return values[0]
    raise ValueError(f"Search query parameter not found in URL: {url}")


def _fetch_cse_config(client: httpx.Client, cx: str) -> dict:
    """Fetch cse.js and extract the short-lived token and request metadata."""

    response = client.get(f"https://cse.google.com/cse.js?cx={cx}")
    response.raise_for_status()
    text = response.text
    config = {
        "cse_token": _extract_js_string(text, "cse_token"),
        "cselibVersion": _extract_js_string(text, "cselibVersion"),
        "usqp": _extract_js_string(text, "usqp"),
        "exp": _extract_js_array(text, "exp"),
        "fexp": _extract_js_array(text, "fexp"),
    }
    if not config["cse_token"] or not config["cselibVersion"]:
        raise ValueError("Could not extract Google CSE token metadata")
    return config


def _extract_js_string(text: str, key: str) -> str | None:
    """Extract one JSON string property from the CSE bootstrap script."""

    match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]*)"', text)
    return match.group(1).replace(r"\u003d", "=") if match else None


def _extract_js_array(text: str, key: str) -> list:
    """Extract one JSON array property from the CSE bootstrap script."""

    match = re.search(rf'"{re.escape(key)}"\s*:\s*(\[[^\]]*\])', text)
    if not match:
        return []
    return json.loads(match.group(1))


def _google_cse_element_url(site: SiteConfig, config: dict, query: str, referer_url: str) -> str:
    """Build the Google CSE element endpoint URL."""

    params = {
        "rsz": "filtered_cse",
        "num": "10",
        "hl": "ja",
        "source": "gcsc",
        "cselibv": config["cselibVersion"],
        "cx": site.google_cse_cx,
        "q": query,
        "safe": "off",
        "cse_tok": config["cse_token"],
        "lr": "",
        "cr": "",
        "gl": "",
        "filter": "0",
        "sort": site.google_cse_sort or "",
        "as_oq": "",
        "as_sitesearch": "",
        "exp": ",".join(config.get("exp") or []),
        "fexp": ",".join(str(value) for value in (config.get("fexp") or [])),
        "callback": GoogleCseFetcher.CALLBACK,
        "rurl": referer_url,
    }
    return "https://cse.google.com/cse/element/v1?" + urlencode(params)


def _parse_google_cse_jsonp(text: str, callback: str) -> dict:
    """Parse a Google CSE JSONP response."""

    text = text.strip()
    prefix = "/*O_o*/\n"
    if text.startswith(prefix):
        text = text[len(prefix) :]
    if not text.startswith(callback):
        raise ValueError("Unexpected Google CSE callback")
    start = text.find("(")
    end = text.rfind(");")
    if start < 0 or end < 0:
        raise ValueError("Malformed Google CSE JSONP response")
    return json.loads(text[start + 1 : end])


def _raise_for_google_cse_error(payload: dict, request: httpx.Request) -> None:
    """Raise an HTTP-like exception when Google CSE returns an error payload."""

    error = payload.get("error")
    if not isinstance(error, dict):
        return

    raw_code = error.get("code")
    try:
        status_code = int(raw_code)
    except (TypeError, ValueError):
        status_code = 502
    if not 100 <= status_code <= 599:
        status_code = 502

    message = str(error.get("message") or "Google CSE returned an error payload")
    response = httpx.Response(status_code, request=request, text=message)
    raise httpx.HTTPStatusError(
        f"Google CSE error {status_code}: {message}",
        request=request,
        response=response,
    )


def _google_cse_payload_to_html(payload: dict) -> str:
    """Convert Google CSE JSON results into parser-compatible HTML."""

    parts = ["<!doctype html><html><body>"]
    for result in payload.get("results") or []:
        title = html.escape(result.get("titleNoFormatting") or result.get("title") or "")
        url = html.escape(result.get("unescapedUrl") or result.get("url") or "")
        snippet = html.escape(
            result.get("contentNoFormatting") or result.get("content") or ""
        )
        if not url:
            continue
        parts.append(
            '<div class="gsc-webResult gsc-result">'
            '<div class="gs-webResult gs-result">'
            f'<a class="gs-title" href="{url}">{title}</a>'
            '<div class="gsc-table-result">'
            '<div class="gsc-table-cell-snippet-close">'
            f'<div class="gs-bidi-start-align gs-snippet">{snippet}</div>'
            "</div></div></div></div>"
        )
    parts.append("</body></html>")
    return "".join(parts)
