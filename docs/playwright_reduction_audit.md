# Playwright Reduction Audit

調査日: 2026-06-21

対象は、現設定で `requires_playwright: true` または `fetch_strategy: playwright*` だった有効サイト。
検索語は `トヨタ`。

| site_id | サイト | HTTP取得結果 | 判定 | 対応 |
|---|---|---|---|---|
| asahi | 朝日新聞デジタル | `sitesearch.asahi.com` のHTTP HTMLには検索結果DOMがなく、`#SiteSearchResult` は0件。外部検索JS `rusk.min.js` 依存。 | Playwright維持 | 未変更 |
| sankei | 産経ニュース | HTTP HTMLに `article` はあるが、検索語を含まず、検索結果ではなく一般記事一覧に近い。 | Playwright維持 | 未変更 |
| nishinippon | 西日本新聞me | HTTP HTMLに検索結果 `article` が存在し、タイトル・URL・掲載日を取得可能。 | HTTP化可 | `requires_playwright: false`, `fetch_strategy: httpx` |
| kumamoto_nichi | 熊本日日新聞 | HTTP HTMLに `.y2024-news-list__item` が存在し、タイトル・URL・掲載日を取得可能。 | HTTP化可 | `requires_playwright: false`, `fetch_strategy: httpx` |
| ehime_np | 愛媛新聞 | HTTP HTMLにリンクは出るが、現selectorは広く、PR/外部提供を含む検索結果全体の妥当性を追加検証したい。 | 保留 | 未変更 |
| nikkei_business | 日経ビジネス | HTTP HTMLに記事カードは出るが、検索語を含まず、検索語に対する結果ではない可能性が高い。 | Playwright維持 | 未変更 |
| nikkei_xtech | 日経クロステック | HTTP HTMLは検索タイトルを含むが、現DOMの `li.articleList_item` は雑誌リンク等で、記事結果URL `/atcl/` ではない。 | Playwright維持 | 未変更 |
| kentsu | 建通新聞 | `fulltext` GETでは結果DOMなし。フォーム送信または内部リクエストの追加調査が必要。 | Playwrightフォーム維持 | 未変更 |

結果:

- 有効サイト: 47
- HTTP取得: 37
- Google CSE直接取得: 4
- Playwright: 5
- Playwrightフォーム: 1
- Playwright依存合計: 6

今回の確定削減:

- `nishinippon`
- `kumamoto_nichi`

残りの追加調査候補:

- `ehime_np`: HTTPで結果らしき一覧は取得できるため、検索結果コンテナと除外条件を精査すればHTTP化できる可能性あり。
- `kentsu`: フォーム送信時のHTTPリクエストを特定できればHTTP化できる可能性あり。
