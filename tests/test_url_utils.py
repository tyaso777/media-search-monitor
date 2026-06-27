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


def test_canonicalize_kobe_np_redirect_url_keeps_go_and_removes_rid():
    base = (
        "https://searching.kobe-np.co.jp/go.php?"
        "go=cpos8rimVaX8rn%2FhwnQZuPImmdJyrtrxyzr3Gn09VmF6IPMMbho%2BxOKzvM29Fvpg6ZhCMqnbBqfsZCKuI%2Bv8ngl0mJlbin9HzxjJBcnH5wQ%3D%26f%3Dr"
    )
    first = f"{base}&rid=1538379902813946"
    second = f"{base}&rid=1538379898902206"

    assert canonicalize_url(first, site_id="kobe_np") == canonicalize_url(
        second, site_id="kobe_np"
    )
    assert canonicalize_url(first, site_id="kobe_np").startswith(
        "https://searching.kobe-np.co.jp/go.php?go="
    )
    assert "rid=" not in canonicalize_url(first, site_id="kobe_np")


def test_canonicalize_sanyo_article_url_removes_search_keyword():
    url = "https://www.sanyonews.jp/article/1892624?kw=AI%E5%B0%8E%E5%85%A5"

    assert canonicalize_url(url, site_id="sanyo") == "https://www.sanyonews.jp/article/1892624"


def test_canonicalize_sakigake_article_url_keeps_article_id_only():
    url = (
        "https://www.sakigake.jp/news/article.jsp?"
        "kc=20260522AK0024&ptxt=TOYOTA&pak=1&pnw=0&psel=all"
    )

    assert (
        canonicalize_url(url, site_id="sakigake")
        == "https://www.sakigake.jp/news/article.jsp?kc=20260522AK0024"
    )


def test_canonicalize_nikkei_business_article_url_removes_navigation_parameter():
    url = "https://business.nikkei.com/atcl/gen/19/00419/061200238/?i_cid=nbpnb_top_rpane_video"

    assert (
        canonicalize_url(url, site_id="nikkei_business")
        == "https://business.nikkei.com/atcl/gen/19/00419/061200238"
    )


def test_encode_query_uses_percent_encoding():
    assert encode_query("トヨタ 自動車") == "%E3%83%88%E3%83%A8%E3%82%BF%20%E8%87%AA%E5%8B%95%E8%BB%8A"
