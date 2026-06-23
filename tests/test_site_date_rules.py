from __future__ import annotations

import yaml

from news_monitor.config import load_sites
from news_monitor.date_utils import SUPPORTED_DATE_RULES, normalize_published_date
from news_monitor.fetcher import SUPPORTED_FETCH_STRATEGIES
from news_monitor.parser import (
    SUPPORTED_DATE_STRATEGIES,
    SUPPORTED_PARSER_STRATEGIES,
    parse_article_published_date,
    parse_search_results,
)


def test_every_enabled_site_has_supported_date_rule(repo_root):
    sites = [site for site in load_sites(repo_root / "config" / "sites.yaml") if site.enabled]
    assert sites
    for site in sites:
        assert site.fetch_strategy in SUPPORTED_FETCH_STRATEGIES
        assert site.date_rule in SUPPORTED_DATE_RULES
        assert site.parser_strategy in SUPPORTED_PARSER_STRATEGIES
        assert site.date_strategy in SUPPORTED_DATE_STRATEGIES


def test_date_rules_file_covers_every_enabled_site(repo_root):
    sites = [site for site in load_sites(repo_root / "config" / "sites.yaml") if site.enabled]
    raw = yaml.safe_load((repo_root / "config" / "date_rules.yaml").read_text(encoding="utf-8"))
    configured = {item["site_id"] for item in raw["rules"]}
    assert {site.site_id for site in sites} <= configured


def test_site_specific_yearless_rules_are_opt_in(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    reference = "2026-06-20T12:00:00+09:00"

    assert sites["kahoku"].date_rule == "url_date_or_explicit_year"

    assert sites["shimotsuke"].date_rule == "current_day_or_current_year_if_yearless"
    assert normalize_published_date("20:30", reference, sites["shimotsuke"].date_rule) == "2026/06/20"
    assert normalize_published_date("6/18 17:03", reference, sites["shimotsuke"].date_rule) == "2026/06/18"
    assert normalize_published_date("2025/9/26", reference, sites["shimotsuke"].date_rule) == "2025/09/26"

    assert sites["mainichi"].date_rule == "explicit_year_only"
    assert normalize_published_date("6/18 17:03", reference, sites["mainichi"].date_rule) is None


def test_toonippo_time_only_strings_are_current_day(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    reference = "2026-06-20T12:00:00+09:00"

    assert sites["toonippo"].date_rule == "current_day_if_time_only"
    assert normalize_published_date("0:39更新", reference, sites["toonippo"].date_rule) == "2026/06/20"
    assert normalize_published_date("6/18 23:45更新", reference, sites["toonippo"].date_rule) is None


def test_kanaloco_fixture_extracts_year_qualified_card_dates(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    html = (repo_root / "work" / "site_html" / "kanaloco.html").read_text(
        encoding="utf-8",
        errors="replace",
    )

    results = parse_search_results(html, sites["kanaloco"], "https://www.kanaloco.jp/search")

    assert results
    assert results[0].published_date
    assert normalize_published_date(results[0].published_date, None, sites["kanaloco"].date_rule)


def test_kumamoto_fixture_extracts_year_qualified_card_dates(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    html = (repo_root / "work" / "playwright_html" / "kumamoto_nichi_fixed.html").read_text(
        encoding="utf-8",
        errors="replace",
    )

    results = parse_search_results(html, sites["kumamoto_nichi"], "https://kumanichi.com/search/cse")

    assert results
    assert results[0].published_date
    assert normalize_published_date(
        results[0].published_date,
        None,
        sites["kumamoto_nichi"].date_rule,
    )


def test_nikkei_fixture_extracts_pubdate_from_search_card_meta(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    html = (repo_root / "tests" / "fixtures" / "nikkei_search_result.html").read_text(
        encoding="utf-8"
    )

    results = parse_search_results(html, sites["nikkei"], "https://www.nikkei.com/search")

    assert len(results) == 1
    assert results[0].title == "誰でも参加OKの朝活、個人で続けまちを元気に　井上・山形市副市長"
    assert results[0].url == "https://www.nikkei.com/article/DGXZQOCC033HU0T00C26A6000000/"
    assert results[0].published_date == "2026-06-21T05:00:00+09:00"
    assert (
        normalize_published_date(results[0].published_date, None, sites["nikkei"].date_rule)
        == "2026/06/21"
    )


def test_nikkei_business_fixture_extracts_rendered_card_dates(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["nikkei_business"]
    html = (repo_root / "tests" / "fixtures" / "nikkei_business_search_result.html").read_text(
        encoding="utf-8"
    )

    assert site.requires_playwright is True
    assert site.fetch_strategy == "playwright"
    assert site.result_item_selector == "section.p-articleList_item"
    assert site.date_selector == ".p-articleList_item_date"

    results = parse_search_results(
        html,
        site,
        "https://business.nikkei.com/search/?KEYWORD=toyota",
    )

    assert len(results) == 1
    assert results[0].title == "日経平均7万円突破 動画で振り返る時価総額ランキング10年 トヨタ1強時代の終幕"
    assert results[0].url == "https://business.nikkei.com/atcl/gen/19/00611/061900050/"
    assert results[0].published_date == "2026.06.19"
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2026/06/19"


def test_nikkei_xtech_fixture_extracts_rendered_card_dates(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["nikkei_xtech"]
    html = (repo_root / "tests" / "fixtures" / "nikkei_xtech_search_result.html").read_text(
        encoding="utf-8"
    )

    assert site.requires_playwright is True
    assert site.fetch_strategy == "playwright"
    assert site.result_item_selector == "li.articleList_item"
    assert site.url_selector == ".articleList_item_title a[href*='/atcl/']"
    assert site.date_selector == "time.articleList_item_date"

    results = parse_search_results(
        html,
        site,
        "https://xtech.nikkei.com/search/?KEYWORD=toyota",
    )

    assert len(results) == 1
    assert results[0].title == "AI investment keeps rising at SoftBank Group"
    assert (
        results[0].url
        == "https://xtech.nikkei.com/atcl/nxt/mag/nc/18/052100110/061800180/"
    )
    assert results[0].published_date == "2026.06.19"
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2026/06/19"


def test_diamond_fixture_extracts_search_result_dates(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["diamond"]
    html = (repo_root / "tests" / "fixtures" / "diamond_search_result.html").read_text(
        encoding="utf-8"
    )

    assert site.search_url_template == "https://diamond.jp/list/search?fulltext={query}"
    assert site.result_item_selector == ".article-list-eh > a[href*='/articles/-/']"
    assert site.date_selector == "time.published"
    assert site.date_rule == "explicit_year_only"

    results = parse_search_results(
        html,
        site,
        "https://diamond.jp/list/search?fulltext=toyota",
    )

    assert len(results) == 1
    assert results[0].title == "Why Nissan lost to Toyota in Indonesia"
    assert results[0].url == "https://diamond.jp/articles/-/392777"
    assert results[0].published_date == "2026年6月19日 4:40"
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2026/06/19"


def test_kentsu_fixture_extracts_form_search_result_dates(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["kentsu"]
    html = (repo_root / "tests" / "fixtures" / "kentsu_search_result.html").read_text(
        encoding="utf-8"
    )

    assert site.requires_playwright is True
    assert site.fetch_strategy == "playwright_form"
    assert site.form_input_selector == "#keyword-input"
    assert site.form_submit_selector == "form button[type=submit]"
    assert site.form_submit_index == -1
    assert site.search_url_template == (
        "https://digital.kentsu.co.jp/articles/artcl_allartcllist?fulltext={query}"
    )
    assert site.result_item_selector == "a[href*='/articles/artcl_rglr/']"
    assert site.title_selector == "h2"
    assert site.date_selector == "time"
    assert site.date_rule == "current_year_if_yearless"

    results = parse_search_results(
        html,
        site,
        "https://digital.kentsu.co.jp/articles/artcl_allartcllist?fulltext=toyota",
    )

    assert len(results) == 2
    assert results[0].title == "Personnel change at Toyota Home"
    assert (
        results[0].url
        == "https://digital.kentsu.co.jp/articles/artcl_rglr/01KVD0FVYANASG28XP4REN2K04"
    )
    assert results[0].published_date == "6/18 20:37"
    assert (
        normalize_published_date(
            results[0].published_date,
            "2026-06-21T12:00:00+09:00",
            site.date_rule,
        )
        == "2026/06/18"
    )
    assert results[1].published_date == "2025/12/01 09:00"
    assert normalize_published_date(results[1].published_date, None, site.date_rule) == "2025/12/01"


def test_tokyo_np_uses_correct_search_endpoint_and_google_cse_result_dates(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["tokyo_np"]

    assert site.search_url_template == "https://www.tokyo-np.co.jp/search_result?q={query}"
    assert site.requires_playwright is False
    assert site.fetch_strategy == "google_cse"
    assert site.google_cse_lightweight_candidate is True
    assert site.google_cse_cx == "ec5a58b709f62d071"
    assert site.date_strategy == "css_selector"
    assert site.date_rule == "relative_japanese_or_explicit_year"

    html = (repo_root / "tests" / "fixtures" / "tokyo_np_search_result.html").read_text(
        encoding="utf-8"
    )
    results = parse_search_results(html, site, "https://www.tokyo-np.co.jp/search_result?q=toyota")

    assert len(results) == 1
    assert results[0].url == "https://www.tokyo-np.co.jp/article/495673"
    assert results[0].published_date.startswith("3日前")
    assert (
        normalize_published_date(
            results[0].published_date,
            "2026-06-21T12:00:00+09:00",
            site.date_rule,
        )
        == "2026/06/18"
    )

    article_html = (repo_root / "tests" / "fixtures" / "tokyo_np_article.html").read_text(
        encoding="utf-8"
    )
    article_date = parse_article_published_date(article_html)

    assert article_date == "2026-06-17T19:15:38+09:00"
    assert normalize_published_date(article_date, None, site.date_rule) == "2026/06/17"


def test_chunichi_uses_correct_search_endpoint_and_google_cse_result_dates(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["chunichi"]

    assert site.search_url_template == "https://www.chunichi.co.jp/search_result?q={query}"
    assert site.requires_playwright is False
    assert site.fetch_strategy == "google_cse"
    assert site.google_cse_lightweight_candidate is True
    assert site.google_cse_cx == "001739771653228343839:pwqh-bnpw8a"
    assert site.date_strategy == "css_selector"
    assert site.date_rule == "relative_japanese_or_explicit_year"

    html = (repo_root / "tests" / "fixtures" / "chunichi_search_result.html").read_text(
        encoding="utf-8"
    )
    results = parse_search_results(html, site, "https://www.chunichi.co.jp/search_result?q=toyota")

    assert len(results) == 2
    assert results[0].url == "https://www.chunichi.co.jp/article/1268660"
    assert results[0].published_date.startswith("3日前")
    assert (
        normalize_published_date(
            results[0].published_date,
            "2026-06-21T12:00:00+09:00",
            site.date_rule,
        )
        == "2026/06/18"
    )
    assert results[1].url == "https://www.chunichi.co.jp/article/1265399"
    assert normalize_published_date(results[1].published_date, None, site.date_rule) == "2026/06/11"


def test_denki_shimbun_uses_google_cse_and_article_date_fallback(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["denki_shimbun"]

    assert site.search_url_template == (
        "https://www.denkishimbun.com/s_result?cof=FORID%3A10&ie=UTF-8&q={query}&sa="
    )
    assert site.requires_playwright is False
    assert site.fetch_strategy == "google_cse"
    assert site.google_cse_lightweight_candidate is True
    assert site.google_cse_cx == "006048404399787863357:x2karccg12w"
    assert site.date_strategy == "css_selector"
    assert site.date_rule == "explicit_year_only"

    html = (
        repo_root / "tests" / "fixtures" / "denki_shimbun_google_cse_result.html"
    ).read_text(encoding="utf-8")
    results = parse_search_results(
        html,
        site,
        "https://www.denkishimbun.com/s_result?cof=FORID%3A10&ie=UTF-8&q=toyota&sa=",
    )

    assert len(results) == 2
    assert results[0].url == "https://www.denkishimbun.com/sp/115948"
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2021/03/25"
    assert results[1].url == "https://www.denkishimbun.com/archives/408584"
    assert normalize_published_date(results[1].published_date, None, site.date_rule) is None

    article_html = (repo_root / "tests" / "fixtures" / "denki_shimbun_article.html").read_text(
        encoding="utf-8"
    )
    article_date = parse_article_published_date(article_html)

    assert article_date == "2026-06-02T06:00:00+09:00"
    assert normalize_published_date(article_date, None, site.date_rule) == "2026/06/02"
