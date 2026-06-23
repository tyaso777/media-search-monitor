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


def canonicalize_url(url: str, base_url: str | None = None) -> str:
    """Normalize URL identity for duplicate detection.

    Args:
        url: URL to normalize.
        base_url: Optional base URL used for relative URLs.

    Returns:
        Canonical URL string.
    """

    absolute = urljoin(base_url, url) if base_url else url
    parts = urlsplit(absolute)
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
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
