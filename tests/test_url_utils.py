from __future__ import annotations

from news_monitor.url_utils import canonicalize_url, encode_query


def test_canonicalize_url_removes_tracking_fragment_and_sorts_query():
    url = "HTTPS://Example.COM/path/?b=2&utm_source=x&a=1#section"

    assert canonicalize_url(url) == "https://example.com/path?a=1&b=2"


def test_canonicalize_relative_url_with_base():
    url = "../article/1?gclid=abc&z=9"
    base_url = "https://example.com/search/results?q=test"

    assert canonicalize_url(url, base_url) == "https://example.com/article/1?z=9"


def test_canonicalize_jiji_article_url_removes_section_parameter_only():
    url = "https://www.jiji.com/jc/article?g=eco&k=2025070800590"

    assert (
        canonicalize_url(url, site_id="jiji")
        == "https://www.jiji.com/jc/article?k=2025070800590"
    )


def test_encode_query_uses_percent_encoding():
    assert encode_query("トヨタ 自動車") == "%E3%83%88%E3%83%A8%E3%82%BF%20%E8%87%AA%E5%8B%95%E8%BB%8A"
