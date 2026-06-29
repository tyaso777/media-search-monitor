from __future__ import annotations

import yaml

from news_monitor.config import load_sites
from news_monitor.date_utils import SUPPORTED_DATE_RULES, best_published_date, normalize_published_date
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


def test_minyu_scopes_results_to_search_thumbnail_list(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["minyu"]
    html = """
    <section class="top-news primary">
      <h1 class="category-title">「トヨタ」の検索結果</h1>
      <ul class="thumbnail-list wide">
        <li class="column column-sp">
          <div class="text-wrap">
            <p class="title">
              <a href="https://www.minyu-net.com/newspack/detail/2026062601001007">
                トヨタ日産、大雨影響の工場再開
              </a>
            </p>
            <div class="status"><p class="day">2026/06/26 13:16</p></div>
          </div>
        </li>
      </ul>
    </section>
    <div class="ranking pc">
      <a class="column column-sp" href="https://www.minyu-net.com/news/detail/2026062618341351545">
        <div class="text-wrap">
          <p class="title">上司にパワハラ、患者虐待...いわき病院の男性職員を停職処分</p>
          <div class="status"><p class="day">2026/06/27 07:50</p></div>
        </div>
      </a>
    </div>
    """

    assert site.result_container_selector == "section.top-news.primary ul.thumbnail-list.wide"
    assert site.result_item_selector == "li.column.column-sp"

    results = parse_search_results(
        html,
        site,
        "https://www.minyu-net.com/search/?q=toyota",
    )

    assert len(results) == 1
    assert results[0].title == "トヨタ日産、大雨影響の工場再開"
    assert results[0].url == "https://www.minyu-net.com/newspack/detail/2026062601001007"
    assert results[0].published_date == "2026/06/26 13:16"
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2026/06/26"


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


def test_jiji_uses_google_cse_and_article_url_filter(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["jiji"]

    assert site.enabled is True
    assert site.search_url_template == "https://www.jiji.com/jc/cse?q={query}"
    assert site.requires_playwright is False
    assert site.fetch_strategy == "google_cse"
    assert site.google_cse_lightweight_candidate is True
    assert site.google_cse_cx == "eeb1e5dc176b1d4dd"
    assert site.result_item_selector == ".gsc-webResult.gsc-result"
    assert site.url_selector == "a.gs-title[href]"
    assert site.date_selector == ".gs-snippet"
    assert site.date_rule == "relative_japanese_or_explicit_year"
    assert site.require_keyword_in_result is False

    html = (repo_root / "tests" / "fixtures" / "jiji_google_cse_result.html").read_text(
        encoding="utf-8"
    )
    results = parse_search_results(html, site, "https://www.jiji.com/jc/cse?q=toyota")

    assert len(results) == 2
    assert results[0].url == "https://www.jiji.com/jc/article?k=2026061700114&g=eco"
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2026/06/17"
    assert results[1].url == "https://www.jiji.com/jc/article?k=2026062300145&g=eco"
    assert (
        best_published_date(
            results[1].published_date,
            results[1].title,
            results[1].snippet,
            "2026-06-27T12:00:00+09:00",
            site.date_rule,
            results[1].url,
        )
        == "2026/06/23"
    )


def test_impress_watch_uses_google_cse_and_watch_subdomain_article_filter(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["impress_watch"]

    assert site.enabled is True
    assert site.search_url_template == "https://www.watch.impress.co.jp/extra/ipw/search/?q={query}"
    assert site.requires_playwright is False
    assert site.fetch_strategy == "google_cse"
    assert site.google_cse_lightweight_candidate is True
    assert site.google_cse_cx == "partner-pub-5723665484085034:7752189602"
    assert site.result_item_selector == ".gsc-webResult.gsc-result"
    assert site.url_selector == "a.gs-title[href]"
    assert site.date_selector == ".gs-snippet"
    assert site.date_rule == "explicit_year_only"
    assert site.require_keyword_in_result is False
    assert "watch.impress.co.jp/docs/" in site.url_include_patterns
    assert "/docs/news/ranking/" in site.url_exclude_patterns

    html = (
        repo_root / "tests" / "fixtures" / "impress_watch_google_cse_result.html"
    ).read_text(encoding="utf-8")
    results = parse_search_results(
        html,
        site,
        "https://www.watch.impress.co.jp/extra/ipw/search/?q=NTT",
    )

    assert len(results) == 2
    assert results[0].url == "https://internet.watch.impress.co.jp/docs/event/2058337.html"
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2025/10/28"
    assert results[1].url == "https://cloud.watch.impress.co.jp/docs/news/2077990.html"
    assert normalize_published_date(results[1].published_date, None, site.date_rule) == "2026/01/15"


def test_kyodo_uses_archive_card_selectors_and_dotted_dates(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["kyodo"]

    assert site.result_container_selector == "main"
    assert site.result_item_selector == ".main_archive__content"
    assert site.title_selector == ".main_archive__content--ttl"
    assert site.url_selector == ".main_archive__content--ttl[href]"
    assert site.date_selector == "time.main_date"
    assert site.snippet_selector == ".main_archive__content--subtext"
    assert site.require_keyword_in_result is False

    html = (repo_root / "tests" / "fixtures" / "kyodo_search_result.html").read_text(
        encoding="utf-8"
    )
    results = parse_search_results(html, site, "https://www.kyodo.co.jp/?s=NTT")

    assert len(results) == 1
    assert results[0].title == "mMEDICI, NTT Precision Medicine and PRiME-R form partnership"
    assert results[0].url == "https://www.kyodo.co.jp/pr/2026-06-25_4018710/"
    assert results[0].published_date.startswith("2026.06.25")
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2026/06/25"


def test_denshi_device_uses_search_result_card_container(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["denshi_device"]

    assert site.result_container_selector == ".main-contents.single-contents.dd-main-content"
    assert site.result_item_selector == "article"
    assert site.title_selector == "h3.title a"
    assert site.url_selector == "h3.title a[href^='https://dempa-digital.com/article/']"
    assert site.date_selector == "ul.post-meta li.date"
    assert site.require_keyword_in_result is False

    html = (repo_root / "tests" / "fixtures" / "denshi_device_search_result.html").read_text(
        encoding="utf-8"
    )
    results = parse_search_results(html, site, "https://dempa-digital.com/?s=NTT")

    assert len(results) == 1
    assert results[0].title == "NTT West to open next-generation AI-ready data centers"
    assert results[0].url == "https://dempa-digital.com/article/718877"
    assert results[0].published_date == "2026.06.23"
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2026/06/23"


def test_shokuhin_sangyo_uses_news_article_cards(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["shokuhin_sangyo"]

    assert site.result_container_selector == ".main-column"
    assert site.result_item_selector == "article.news-article-item"
    assert site.title_selector == ".article-title"
    assert site.url_selector == ".article-text > a[href^='https://www.ssnp.co.jp/']"
    assert site.date_selector == ".article-date"
    assert site.snippet_selector == ".article-excerpt"
    assert site.require_keyword_in_result is False

    html = (repo_root / "tests" / "fixtures" / "shokuhin_sangyo_search_result.html").read_text(
        encoding="utf-8"
    )
    results = parse_search_results(html, site, "https://www.ssnp.co.jp/?s=toyota")

    assert len(results) == 1
    assert results[0].title == "Nescafe sleep cafe collaborates with Toyota nap tool"
    assert results[0].url == "https://www.ssnp.co.jp/beverage/628286/"
    assert results[0].published_date == "2025年8月22日"
    assert results[0].snippet == "Nescafe and Toyota developed a tool for short breaks."
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2025/08/22"


def test_nikkan_jidosha_uses_scoped_search_result_cards(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["nikkan_jidosha"]

    assert site.enabled is True
    assert site.search_url_template == "https://www.netdenjd.com/?s={query}"
    assert site.result_container_selector == ".search-reslut-contents"
    assert site.result_item_selector == ".post_content"
    assert site.title_selector == "h5.clearfix > a"
    assert site.url_selector == "h5.clearfix > a"
    assert site.date_selector == "ul.post_details.simple span.date"
    assert site.snippet_selector == "ul.post_details.simple"
    assert site.date_rule == "explicit_year_only"
    assert site.require_keyword_in_result is False

    html = (repo_root / "tests" / "fixtures" / "nikkan_jidosha_search_result.html").read_text(
        encoding="utf-8"
    )
    results = parse_search_results(html, site, "https://www.netdenjd.com/?s=toyota")

    assert len(results) == 1
    assert results[0].title == "Toyota industry primer"
    assert results[0].url == "https://www.netdenjd.com/archives/676767"
    assert results[0].published_date == "2026年6月29日 05:00"
    assert "Automotive makers" in (results[0].snippet or "")
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2026/06/29"


def test_shizushin_uses_news_at_s_search_result_cards(repo_root):
    sites = {site.site_id: site for site in load_sites(repo_root / "config" / "sites.yaml")}
    site = sites["shizushin"]

    assert site.enabled is True
    assert site.search_url_template == "https://news.at-s.com/search/list?keyword={query}"
    assert site.result_container_selector == ".list-inner"
    assert site.result_item_selector == ".newslistbox"
    assert site.title_selector == ".news-ttle a.overlay-link"
    assert site.url_selector == ".news-ttle a.overlay-link[href^='/article/']"
    assert site.date_selector == "p.date time[datetime]"
    assert site.snippet_selector is None
    assert site.date_rule == "machine_datetime"
    assert site.require_keyword_in_result is False

    html = (repo_root / "tests" / "fixtures" / "shizushin_search_result.html").read_text(
        encoding="utf-8"
    )
    results = parse_search_results(html, site, "https://news.at-s.com/search/list?keyword=NTT")

    assert len(results) == 1
    assert results[0].title == "Major mobile carriers use AI for bear countermeasures"
    assert results[0].url == "https://news.at-s.com/article/1996106"
    assert results[0].published_date == "2026-06-18T15:40:00+09:00"
    assert normalize_published_date(results[0].published_date, None, site.date_rule) == "2026/06/18"


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
