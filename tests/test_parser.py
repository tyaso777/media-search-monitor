from __future__ import annotations

from dataclasses import replace

from news_monitor.config import load_sites
from news_monitor.parser import parse_article_published_date, parse_search_results


def test_parse_sample_search_results(repo_root, fixture_html):
    site = load_sites(repo_root / "config" / "sites.yaml")[0]

    results = parse_search_results(fixture_html, site, "https://example.com/search?q=test")

    assert len(results) == 2
    assert results[0].title == "トヨタが新技術を発表"
    assert results[0].url.startswith("https://example.com/articles/100")
    assert results[0].published_date == "2026-06-19"
    assert "トヨタ自動車" in (results[0].snippet or "")


def test_parser_tolerates_null_optional_selectors(repo_root, fixture_html):
    site = replace(
        load_sites(repo_root / "config" / "sites.yaml")[0],
        title_selector=None,
        date_selector=None,
        snippet_selector=None,
    )

    results = parse_search_results(fixture_html, site, "https://example.com/search?q=test")

    assert results[0].title == "トヨタが新技術を発表"
    assert results[0].published_date is None
    assert results[0].snippet is None


def test_parser_prefers_datetime_attribute(repo_root):
    site = replace(
        load_sites(repo_root / "config" / "sites.yaml")[0],
        result_item_selector=".result",
        title_selector="a",
        url_selector="a",
        date_selector="time",
        snippet_selector=None,
    )
    html = """
    <div class="result">
      <a href="/articles/1">Title</a>
      <time datetime="2026-06-20T09:30:00+09:00">午前9時30分</time>
    </div>
    """

    results = parse_search_results(html, site, "https://example.com/search")

    assert results[0].published_date == "2026-06-20T09:30:00+09:00"


def test_parser_scopes_items_to_result_container(repo_root):
    site = replace(
        load_sites(repo_root / "config" / "sites.yaml")[0],
        result_container_selector="#search-results",
        result_item_selector="article",
        title_selector="a",
        url_selector="a",
        date_selector="time",
        snippet_selector="p",
    )
    html = """
    <aside>
      <article>
        <a href="/articles/sidebar">Sidebar latest item</a>
        <time datetime="2026-06-21">2026-06-21</time>
        <p>Always visible latest news.</p>
      </article>
    </aside>
    <section id="search-results">
      <article>
        <a href="/articles/search-hit">Actual search hit</a>
        <time datetime="2026-06-20">2026-06-20</time>
        <p>Search result snippet.</p>
      </article>
    </section>
    """

    results = parse_search_results(html, site, "https://example.com/search")

    assert len(results) == 1
    assert results[0].title == "Actual search hit"
    assert results[0].url == "https://example.com/articles/search-hit"


def test_parser_returns_no_items_when_no_results_text_is_present(repo_root):
    site = replace(
        load_sites(repo_root / "config" / "sites.yaml")[0],
        no_results_text="No matching articles",
        result_item_selector="article",
        title_selector="a",
        url_selector="a",
    )
    html = """
    <main>No matching articles</main>
    <aside>
      <article><a href="/articles/sidebar">Sidebar latest item</a></article>
    </aside>
    """

    results = parse_search_results(html, site, "https://example.com/search")

    assert results == []


def test_site_specific_parser_strategy_requires_registered_parser(repo_root, fixture_html):
    site = replace(
        load_sites(repo_root / "config" / "sites.yaml")[0],
        parser_strategy="site_specific",
    )

    try:
        parse_search_results(fixture_html, site, "https://example.com/search?q=test")
    except NotImplementedError as exc:
        assert "site_id=sample_news" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("site_specific parser should require an implementation")


def test_parse_article_published_date_prefers_article_meta():
    html = """
    <html>
      <head>
        <meta property="article:published_time" content="2026-06-20T08:30:00+09:00">
      </head>
      <body><time datetime="2026-06-19T12:00:00+09:00">older</time></body>
    </html>
    """

    assert parse_article_published_date(html) == "2026-06-20T08:30:00+09:00"


def test_parse_article_published_date_reads_json_ld():
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "NewsArticle",
          "headline": "Example",
          "datePublished": "2026-06-20T14:22:21+09:00",
          "dateModified": "2026-06-20T14:40:44+09:00"
        }
        </script>
      </head>
      <body>Article</body>
    </html>
    """

    assert parse_article_published_date(html) == "2026-06-20T14:22:21+09:00"
