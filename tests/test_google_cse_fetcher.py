from __future__ import annotations

from news_monitor.config import load_sites
from news_monitor.date_utils import best_published_date
from news_monitor.fetcher import (
    GoogleCseFetcher,
    _google_cse_payload_to_html,
    _parse_google_cse_jsonp,
)
from news_monitor.parser import parse_search_results


def test_google_cse_jsonp_payload_converts_to_parser_compatible_html(repo_root):
    payload = """
/*O_o*/
google.search.cse.api00000({
  "results": [
    {
      "titleNoFormatting": "\\u30c8\\u30e8\\u30bf\\u3001\\uff11\\uff11\\u4e07\\u53f0\\u30ea\\u30b3\\u30fc\\u30eb - \\u6771\\u4eac\\u65b0\\u805e",
      "unescapedUrl": "https://www.tokyo-np.co.jp/article/495893",
      "contentNoFormatting": "3 \\u65e5\\u524d ... \\u30c8\\u30e8\\u30bf\\u81ea\\u52d5\\u8eca\\u306f18\\u65e5\\u3001\\u30b7\\u30fc\\u30c8\\u30d9\\u30eb\\u30c8\\u3092..."
    }
  ]
});
"""
    data = _parse_google_cse_jsonp(payload, GoogleCseFetcher.CALLBACK)
    html = _google_cse_payload_to_html(data)
    site = next(
        site for site in load_sites(repo_root / "config" / "sites.yaml") if site.site_id == "tokyo_np"
    )

    results = parse_search_results(
        html,
        site,
        "https://www.tokyo-np.co.jp/search_result?q=toyota",
    )

    assert len(results) == 1
    assert results[0].title == "トヨタ、１１万台リコール - 東京新聞"
    assert results[0].url == "https://www.tokyo-np.co.jp/article/495893"
    assert results[0].published_date.startswith("3 日前")


def test_google_cse_itmedia_snippet_dates_normalize_relative_and_explicit_dates(repo_root):
    payload = """
/*O_o*/
google.search.cse.api00000({
  "results": [
    {
      "titleNoFormatting": "ECU\\u306e\\u4e00\\u4f53\\u5316\\u3067\\u9032\\u5316\\u3057\\u305f\\u30c8\\u30e8\\u30bf\\u306e\\u65b0\\u578bRAV4",
      "unescapedUrl": "https://monoist.itmedia.co.jp/mn/articles/2605/28/news058.html",
      "contentNoFormatting": "2026/05/28 ... ECU\\u306e\\u4e00\\u4f53\\u5316\\u3067\\u9032\\u5316\\u3057\\u305f\\u30c8\\u30e8\\u30bf\\u306e\\u65b0\\u578bRAV4"
    },
    {
      "titleNoFormatting": "\\u30b7\\u30fc\\u30c8\\u30d9\\u30eb\\u30c8\\u306b\\u4e0d\\u5177\\u5408",
      "unescapedUrl": "https://monoist.itmedia.co.jp/mn/articles/2606/19/news061.html",
      "contentNoFormatting": "2 \\u65e5\\u524d ... \\u30c8\\u30e8\\u30bf\\u81ea\\u52d5\\u8eca\\u306f\\u30b7\\u30a8\\u30f3\\u30bf\\u306e\\u30ea\\u30b3\\u30fc\\u30eb\\u3092\\u56fd\\u571f\\u4ea4\\u901a\\u7701\\u306b\\u5c4a\\u3051\\u51fa\\u3057\\u305f"
    }
  ]
});
"""
    data = _parse_google_cse_jsonp(payload, GoogleCseFetcher.CALLBACK)
    html = _google_cse_payload_to_html(data)
    site = next(
        site for site in load_sites(repo_root / "config" / "sites.yaml") if site.site_id == "itmedia"
    )

    results = parse_search_results(
        html,
        site,
        "https://cse.google.com/cse?cx=000492183644671384608%3A6dff3odaltq&q=toyota",
    )

    assert len(results) == 2
    assert results[0].published_date.startswith("2026/05/28")
    assert (
        best_published_date(
            results[0].published_date,
            results[0].title,
            results[0].snippet,
            "2026-06-21T12:00:00+09:00",
            site.date_rule,
            results[0].url,
        )
        == "2026/05/28"
    )
    assert results[1].published_date.startswith("2 日前")
    assert (
        best_published_date(
            results[1].published_date,
            results[1].title,
            results[1].snippet,
            "2026-06-21T12:00:00+09:00",
            site.date_rule,
            results[1].url,
        )
        == "2026/06/19"
    )
