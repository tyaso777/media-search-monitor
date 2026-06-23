"""Date extraction and normalization helpers."""

from __future__ import annotations

import re
from datetime import datetime, timedelta


DATE_PATTERNS = [
    re.compile(r"(?P<year>20\d{2})[./-](?P<month>\d{1,2})[./-](?P<day>\d{1,2})"),
    re.compile(r"(?P<year>20\d{2})\u5e74(?P<month>\d{1,2})\u6708(?P<day>\d{1,2})\u65e5"),
    re.compile(r"(?P<year>20\d{2})\.(?P<month>\d{1,2})\.(?P<day>\d{1,2})"),
    re.compile(r"(?P<year>\d{2})/(?P<month>\d{1,2})/(?P<day>\d{1,2})"),
]

YEARLESS_DATE_PATTERNS = [
    re.compile(r"(?<!\d)(?P<month>\d{1,2})/(?P<day>\d{1,2})(?!\d)"),
    re.compile(r"(?P<month>\d{1,2})\u6708(?P<day>\d{1,2})\u65e5"),
]

TIME_ONLY_PATTERNS = [
    re.compile(r"^\s*(?P<hour>[0-2]?\d):(?P<minute>[0-5]\d)\s*(?:\u66f4\u65b0)?\s*$"),
]

JAPANESE_RELATIVE_PATTERNS = [
    re.compile(r"(?P<count>[0-9\uff10-\uff19]+)\s*\u6642\u9593\u524d"),
    re.compile(r"(?P<count>[0-9\uff10-\uff19]+)\s*\u65e5\u524d"),
]

URL_DATE_PATTERNS = [
    re.compile(r"(?:^|[^\d])(?P<year>20\d{2})(?P<month>\d{2})(?P<day>\d{2})(?:[^\d]|$)"),
]

SUPPORTED_DATE_RULES = {
    "explicit_year_only",
    "explicit_year_from_snippet",
    "machine_datetime",
    "current_year_if_yearless",
    "current_day_if_time_only",
    "current_day_or_current_year_if_yearless",
    "relative_japanese_or_explicit_year",
    "url_date_or_explicit_year",
    "none",
}


def normalize_published_date(
    text: str | None,
    reference_iso: str | None = None,
    date_rule: str = "explicit_year_only",
) -> str | None:
    """Normalize a published-date string to yyyy/mm/dd using a site-specific rule."""

    if not text:
        return None
    if date_rule not in SUPPORTED_DATE_RULES:
        raise ValueError(f"Unsupported date_rule: {date_rule}")
    normalize_rule = "explicit_year_only" if date_rule == "machine_datetime" else date_rule
    if normalize_rule == "none":
        return None

    compact = " ".join(str(text).split())
    explicit = _normalize_explicit_year(compact)
    if explicit:
        return explicit

    if normalize_rule in {
        "current_year_if_yearless",
        "current_day_or_current_year_if_yearless",
    }:
        yearless = _normalize_yearless_month_day(compact, reference_iso)
        if yearless:
            return yearless

    if normalize_rule in {
        "current_day_if_time_only",
        "current_day_or_current_year_if_yearless",
    }:
        return _normalize_time_only_as_reference_date(compact, reference_iso)

    if normalize_rule == "relative_japanese_or_explicit_year":
        return _normalize_japanese_relative_date(compact, reference_iso)

    return None


def best_published_date(
    published_date: str | None,
    title: str | None,
    snippet: str | None,
    reference_iso: str | None = None,
    date_rule: str = "explicit_year_only",
    url: str | None = None,
) -> str | None:
    """Return the best normalized date from site-approved date fields."""

    if date_rule == "url_date_or_explicit_year":
        url_date = normalize_url_date(url)
        if url_date:
            return url_date
        values = (published_date,)
        normalize_rule = "explicit_year_only"
    elif date_rule == "explicit_year_from_snippet":
        values = (published_date, snippet)
        normalize_rule = "explicit_year_only"
    elif date_rule == "none":
        values = (published_date,)
        normalize_rule = "none"
    elif date_rule == "machine_datetime":
        values = (published_date,)
        normalize_rule = "machine_datetime"
    else:
        values = (published_date,)
        normalize_rule = date_rule

    for value in values:
        normalized = normalize_published_date(value, reference_iso, normalize_rule)
        if normalized:
            return normalized
    return None


def normalize_url_date(url: str | None) -> str | None:
    """Normalize a yyyyMMdd date embedded in a URL path."""

    if not url:
        return None
    for pattern in URL_DATE_PATTERNS:
        match = pattern.search(url)
        if not match:
            continue
        year = int(match.group("year"))
        month = int(match.group("month"))
        day = int(match.group("day"))
        if _valid_month_day(month, day):
            return f"{year:04d}/{month:02d}/{day:02d}"
    return None


def _normalize_explicit_year(text: str) -> str | None:
    """Normalize strings containing an explicit year."""

    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        year = int(match.group("year"))
        if year < 100:
            year += 2000
        month = int(match.group("month"))
        day = int(match.group("day"))
        if not _valid_month_day(month, day):
            continue
        return f"{year:04d}/{month:02d}/{day:02d}"
    return None


def _normalize_yearless_month_day(text: str, reference_iso: str | None) -> str | None:
    """Normalize M/D or M-month D-day strings using the site-approved reference year."""

    reference_year = _reference_year(reference_iso)
    if reference_year is None:
        return None
    for pattern in YEARLESS_DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        month = int(match.group("month"))
        day = int(match.group("day"))
        if not _valid_month_day(month, day):
            continue
        return f"{reference_year:04d}/{month:02d}/{day:02d}"
    return None


def _normalize_time_only_as_reference_date(text: str, reference_iso: str | None) -> str | None:
    """Normalize HH:MM current-day strings using the crawl reference date."""

    reference_date = _reference_date(reference_iso)
    if reference_date is None:
        return None
    for pattern in TIME_ONLY_PATTERNS:
        match = pattern.fullmatch(text)
        if not match:
            continue
        hour = int(match.group("hour"))
        if 0 <= hour <= 23:
            return reference_date
    return None


def _normalize_japanese_relative_date(text: str, reference_iso: str | None) -> str | None:
    """Normalize site-displayed relative Japanese dates such as 3時間前 or 2日前."""

    reference = _reference_datetime(reference_iso)
    if reference is None:
        return None
    for pattern in JAPANESE_RELATIVE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        count = _parse_japanese_number(match.group("count"))
        if count is None:
            return None
        if "\u6642\u9593\u524d" in match.group(0):
            resolved = reference - timedelta(hours=count)
        else:
            resolved = reference - timedelta(days=count)
        return f"{resolved.year:04d}/{resolved.month:02d}/{resolved.day:02d}"
    return None


def _parse_japanese_number(value: str) -> int | None:
    """Parse ASCII or full-width digit strings."""

    normalized = value.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if not normalized.isdigit():
        return None
    return int(normalized)


def _reference_year(reference_iso: str | None) -> int | None:
    """Extract the crawl reference year used by current-year date rules."""

    reference = _reference_datetime(reference_iso)
    if reference:
        return reference.year
    if not reference_iso:
        return None
    match = re.search(r"(20\d{2})", reference_iso)
    return int(match.group(1)) if match else None


def _reference_date(reference_iso: str | None) -> str | None:
    """Extract the crawl reference date as yyyy/mm/dd."""

    reference = _reference_datetime(reference_iso)
    if not reference:
        return None
    return f"{reference.year:04d}/{reference.month:02d}/{reference.day:02d}"


def _reference_datetime(reference_iso: str | None) -> datetime | None:
    """Parse the crawl reference timestamp."""

    if not reference_iso:
        return None
    try:
        return datetime.fromisoformat(reference_iso)
    except ValueError:
        return None


def _valid_month_day(month: int, day: int) -> bool:
    """Return true for plausible calendar month/day values."""

    return 1 <= month <= 12 and 1 <= day <= 31
