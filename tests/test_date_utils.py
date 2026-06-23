from __future__ import annotations

from news_monitor.date_utils import best_published_date, normalize_published_date


def test_normalize_published_date_requires_explicit_year_by_default():
    assert normalize_published_date("2026-06-20T09:30:00+09:00") == "2026/06/20"
    assert normalize_published_date("2026年6月20日 8:41") == "2026/06/20"
    assert normalize_published_date("2026.06.19") == "2026/06/19"
    assert normalize_published_date("26/06/19") == "2026/06/19"
    assert normalize_published_date("6月20日 8:41", "2026-06-20T12:00:00+09:00") is None
    assert normalize_published_date("6/19 23:05", "2026-06-20T12:00:00+09:00") is None
    assert normalize_published_date("11:30", "2026-06-20T12:00:00+09:00") is None
    assert normalize_published_date("11:00更新", "2026-06-20T12:00:00+09:00") is None


def test_current_year_rule_normalizes_yearless_month_day_only():
    assert (
        normalize_published_date(
            "6月20日 8:41",
            "2026-06-20T12:00:00+09:00",
            "current_year_if_yearless",
        )
        == "2026/06/20"
    )
    assert (
        normalize_published_date(
            "6/19 23:05",
            "2026-06-20T12:00:00+09:00",
            "current_year_if_yearless",
        )
        == "2026/06/19"
    )
    assert (
        normalize_published_date(
            "11:30",
            "2026-06-20T12:00:00+09:00",
            "current_year_if_yearless",
        )
        is None
    )


def test_current_day_or_current_year_rule_handles_time_only_today():
    assert (
        normalize_published_date(
            "0:39更新",
            "2026-06-20T12:00:00+09:00",
            "current_day_or_current_year_if_yearless",
        )
        == "2026/06/20"
    )
    assert (
        normalize_published_date(
            "6/19 23:05更新",
            "2026-06-20T12:00:00+09:00",
            "current_day_or_current_year_if_yearless",
        )
        == "2026/06/19"
    )


def test_current_day_only_rule_does_not_infer_yearless_month_day():
    assert (
        normalize_published_date(
            "0:39更新",
            "2026-06-20T12:00:00+09:00",
            "current_day_if_time_only",
        )
        == "2026/06/20"
    )
    assert (
        normalize_published_date(
            "6/19 23:05更新",
            "2026-06-20T12:00:00+09:00",
            "current_day_if_time_only",
        )
        is None
    )


def test_relative_japanese_rule_uses_only_displayed_relative_text():
    reference = "2026-06-21T01:30:00+09:00"

    assert (
        normalize_published_date(
            "3時間前",
            reference,
            "relative_japanese_or_explicit_year",
        )
        == "2026/06/20"
    )
    assert (
        normalize_published_date(
            "２日前",
            reference,
            "relative_japanese_or_explicit_year",
        )
        == "2026/06/19"
    )
    assert (
        normalize_published_date(
            "2026/06/17",
            reference,
            "relative_japanese_or_explicit_year",
        )
        == "2026/06/17"
    )
    assert normalize_published_date(None, reference, "relative_japanese_or_explicit_year") is None
    assert normalize_published_date("", reference, "relative_japanese_or_explicit_year") is None
    assert (
        normalize_published_date(
            "6/19 23:05",
            reference,
            "relative_japanese_or_explicit_year",
        )
        is None
    )


def test_url_date_rule_prefers_embedded_url_date():
    assert (
        best_published_date(
            "6月18日 18:03",
            None,
            None,
            "2026-06-20T12:00:00+09:00",
            "url_date_or_explicit_year",
            "https://kahoku.news/articles/20240501khn000003.html",
        )
        == "2024/05/01"
    )
    assert (
        best_published_date(
            "6月18日 18:03",
            None,
            None,
            "2026-06-20T12:00:00+09:00",
            "url_date_or_explicit_year",
            "https://example.com/articles/no-date.html",
        )
        is None
    )


def test_best_published_date_does_not_use_title_by_default():
    assert (
        best_published_date(
            None,
            "Example title (2026/06/20)",
            None,
            "2026-06-20T12:00:00+09:00",
        )
        is None
    )


def test_best_published_date_can_use_snippet_for_configured_sites():
    assert (
        best_published_date(
            None,
            "Example title (2026/06/20)",
            "2026/06/19 - Example snippet",
            "2026-06-20T12:00:00+09:00",
            "explicit_year_from_snippet",
        )
        == "2026/06/19"
    )
