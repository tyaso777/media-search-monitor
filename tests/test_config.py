from __future__ import annotations

from news_monitor.config import load_app_config, load_keywords, load_sites


def test_load_app_config(repo_root):
    app_config = load_app_config(repo_root / "config" / "app.yaml")

    assert app_config.playwright.enabled is False
    assert app_config.crawler.request_timeout_seconds == 30
    assert app_config.crawler.max_concurrent_sites == 8
    assert app_config.crawler.article_date_lookup_enabled is True
    assert app_config.crawler.article_date_lookup_max_per_site == 30
    assert app_config.report.output_dir == "reports"


def test_load_sites(repo_root):
    sites = load_sites(repo_root / "config" / "sites.yaml")

    site_ids = [site.site_id for site in sites]
    assert site_ids[:2] == ["sample_news", "sample_dynamic_news"]
    assert len(site_ids) >= 40
    assert len(site_ids) == len(set(site_ids))
    assert {"asahi", "nikkei", "hokkaido_np", "nikkan_kogyo"}.issubset(site_ids)
    assert sites[0].enabled is False
    assert sites[0].requires_playwright is False
    assert sites[1].enabled is False
    assert sites[1].requires_playwright is True
    toyokeizai = next(site for site in sites if site.site_id == "toyokeizai")
    assert toyokeizai.search_url_template == "https://toyokeizai.net/list/search?fulltext={query}"
    itmedia = next(site for site in sites if site.site_id == "itmedia")
    assert itmedia.enabled is True
    assert itmedia.requires_playwright is False
    assert itmedia.fetch_strategy == "google_cse"
    assert itmedia.google_cse_lightweight_candidate is True
    assert itmedia.google_cse_cx == "000492183644671384608:6dff3odaltq"
    assert itmedia.search_url_template == (
        "https://cse.google.com/cse?cx=000492183644671384608%3A6dff3odaltq&q={query}"
    )
    denki = next(site for site in sites if site.site_id == "denki_shimbun")
    assert denki.search_url_template == (
        "https://www.denkishimbun.com/s_result?cof=FORID%3A10&ie=UTF-8&q={query}&sa="
    )
    assert denki.fetch_strategy == "google_cse"
    assert denki.google_cse_lightweight_candidate is True
    assert denki.google_cse_cx == "006048404399787863357:x2karccg12w"
    assert "https://www.denkishimbun.com/archives/" in denki.url_include_patterns
    assert "https://www.denkishimbun.com/sp/" in denki.url_include_patterns
    assert "/sp/tag/" in denki.url_exclude_patterns
    logistics = next(site for site in sites if site.site_id == "logistics_today")
    assert logistics.result_item_selector == ".newsList .list"
    assert logistics.url_selector == ".list-heading p a[href^='https://www.logi-today.com/']"
    assert logistics.require_keyword_in_result is True


def test_load_keywords_uses_stable_uuid_style_internal_ids(repo_root):
    keywords = load_keywords(repo_root / "config" / "keywords.csv")

    assert len(keywords) >= 55
    assert keywords[0].source_base_keyword_id == "b001"
    assert keywords[0].source_candidate_keyword_id == "c001"
    assert keywords[0].base_keyword_id.startswith("kwg_")
    assert keywords[0].candidate_keyword_id.startswith("kwc_")
    assert keywords[0].group_type == "company"
    assert keywords[0].base_keyword_id != "b001"
    assert keywords[0].candidate_keyword_id != "c001"
    assert any(keyword.candidate_keyword == "TOYOTA" for keyword in keywords)
