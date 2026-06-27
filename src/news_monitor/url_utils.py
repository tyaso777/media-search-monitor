"""URL normalization helpers."""

from __future__ import annotations

from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}

SITE_QUERY_PARAMS_TO_DROP = {
    "jiji": {"g"},
    "nikkei_business": {"i_cid"},
    "sanyo": {"kw"},
}

SITE_REDIRECT_QUERY_PARAMS_TO_KEEP = {
    ("kobe_np", "searching.kobe-np.co.jp", "/go.php"): {"go"},
    ("sakigake", "www.sakigake.jp", "/news/article.jsp"): {"kc"},
}


def encode_query(query: str, encoding: str = "utf-8") -> str:
    """URL-encode a search query.

    Args:
        query: Raw search query.
        encoding: Text encoding for percent escaping.

    Returns:
        Percent-encoded query.
    """

    return quote(query, safe="", encoding=encoding)


def absolute_url(url: str, base_url: str) -> str:
    """Convert a possibly relative URL to an absolute URL."""

    return urljoin(base_url, url)


def canonicalize_url(url: str, base_url: str | None = None, site_id: str | None = None) -> str:
    """Normalize URL identity for duplicate detection.

    Args:
        url: URL to normalize.
        base_url: Optional base URL used for relative URLs.
        site_id: Optional site ID used for site-specific canonical rules.

    Returns:
        Canonical URL string.
    """

    absolute = urljoin(base_url, url) if base_url else url
    parts = urlsplit(absolute)
    dropped_site_params = SITE_QUERY_PARAMS_TO_DROP.get(site_id or "", set())
    kept_redirect_params = SITE_REDIRECT_QUERY_PARAMS_TO_KEEP.get(
        (site_id or "", parts.netloc.lower(), parts.path or "/")
    )
    query_pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower in TRACKING_PARAMS:
            continue
        if key_lower in dropped_site_params:
            continue
        if kept_redirect_params is not None and key_lower not in kept_redirect_params:
            continue
        query_pairs.append((key, value))
    normalized_query = urlencode(sorted(query_pairs), doseq=True)
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            normalized_query,
            "",
        )
    )
