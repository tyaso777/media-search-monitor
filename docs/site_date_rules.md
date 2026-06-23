# 掲載日抽出ルール

この資料は、検索結果ページ上の掲載日表示と、それに対する抽出・正規化ロジックをサイトごとに記録するものです。機械可読な設定は `config/date_rules.yaml`、selector は `config/site_overrides.yaml` にあります。

## 共通方針

- 全サイト共通で年なし日付を推定しない。
- 年なし・時刻のみの補完は、サイトごとの表示規則が確認できた場合だけ `date_rule` で明示的に許可する。
- `date_selector: null` のサイトでは、タイトル中の年や本文中の数字を掲載日として使わない。
- `time[datetime]` など機械可読属性があるサイトは、表示テキストより属性値を優先する。
- 相対表記の `8時間前` は現時点では正規化しない。クロール時刻から逆算すると日付境界や遅延取得で誤りやすいため。
- 検索結果・URLから掲載日が確定できない場合に限り、記事ページを追加取得して `article:published_time` や `time[datetime]` を確認する。
- 記事ページfallbackは負荷を抑えるため、`article_date_lookup_max_per_site` の上限内でだけ実行する。

## date_rule

| date_rule | 使う状況 | 正規化する値 | 正規化しない値 |
|---|---|---|---|
| `machine_datetime` | `time[datetime]` など機械可読属性がある | `2026-06-20T09:30:00+09:00` | 属性がなく年もない `6/20` |
| `explicit_year_only` | 検索結果の日付テキストに年がある | `2026/06/20`, `2026年6月20日`, `2026.06.20` | `6/20`, `09:30` |
| `current_year_if_yearless` | 今年の記事が `M/D` または `M月D日` で表示される | `6/20`, `6月20日` をクロール基準年で補完 | `09:30` |
| `current_day_if_time_only` | 本日分だけが時刻で表示されることは確認できたが、`M/D` の年は確定できない | `09:30` をクロール基準日で補完 | `6/19`, `6月19日` |
| `current_day_or_current_year_if_yearless` | 本日分が時刻だけ、今年の別日が `M/D`、昨年以前が年付きと確認できた | `09:30` をクロール基準日、`6/19` をクロール基準年で補完 | 相対表記 `8時間前` |
| `relative_japanese_or_explicit_year` | 検索結果が `3時間前` / `2日前` / `yyyy/mm/dd` のように表示される | サイト表示の相対表記をクロール基準時刻から計算、または明示年付き表示 | 年なし `6/19`、日付表示が空の項目 |
| `url_date_or_explicit_year` | 表示が年なしでもURLに `yyyyMMdd` が入る | URL内 `20240501`、または明示年付き表示 | URLにも表示にも年がない値 |
| `explicit_year_from_snippet` | 独立した日付要素がなく、snippetに絶対日付だけを採用する | snippet内の `2026/06/20` | snippet内の `20時間前` |
| `none` | 検索結果カードに信頼できる掲載日がない | なし | すべて `NULL` |

## サイト別ルール

| site_id | サイト上の掲載日表示ロジック | 実装した抽出ロジック | 変化検知テスト |
|---|---|---|---|
| asahi | 現selectorでは検索結果カード内に信頼できる掲載日なし。 | `date_rule: none`。掲載日は保存しない。 | enabled siteが必ずdate_ruleを持つことを検査。 |
| yomiuri | `time[datetime]` に年付き日時。表示も年付き。 | `machine_datetime`。`.c-list-date time[datetime]` の属性値を優先。 | `machine_datetime` がサポート済みルールであることを検査。 |
| mainichi | `2026/6/18 19:11` のように年付き。 | `explicit_year_only`。年なしは採用しない。 | 年なし `6/18` が mainichi では `NULL` になることを検査。 |
| sankei | 検索結果外に日付候補があるが、カード内に安全にscopeできていない。 | `none`。ランキング等の日付を誤取得しない。 | enabled site date_rule網羅テスト。 |
| nikkei | `time[datetime]` に年付き日時。 | `machine_datetime`。属性値を優先。 | ルールサポート検査。 |
| tokyo_np | 正しい検索URLは `/search_result?q=`。検索結果本体はGoogle CSEの `.gsc-webResult.gsc-result` で、`.gs-snippet` 先頭に `3日前 ...` などの相対日付が表示される。 | `requires_playwright: true` + `date_rule: relative_japanese_or_explicit_year`。Playwright後DOMの `.gs-snippet` から相対日付を正規化。記事ページJSON-LD `datePublished` もfallback可。 | `tests/fixtures/tokyo_np_search_result.html` でGoogle CSEカードの `3日前` を検査し、固定基準時刻から `2026/06/18` に正規化できることを検証。 |
| chunichi | 検索URLは `/search_result?q=`。検索結果本体はGoogle CSEの `.gsc-webResult.gsc-result` で、`.gs-snippet` 先頭に `3日前 ...` または `2026/06/11 ...` のような日付が表示される。 | `requires_playwright: true` + `date_rule: relative_japanese_or_explicit_year`。Playwright後DOMの `.gs-snippet` から相対日付または明示年付き日付を正規化。 | `tests/fixtures/chunichi_search_result.html` でGoogle CSEカードの `3日前` と `2026/06/11` を検査。相対日付は固定基準時刻から `2026/06/18` に正規化できることを検証。 |
| hokkaido_np | `.post_date` に `2026年6月18日 17:09`。 | `explicit_year_only`。 | 年付き日本語日付の共通正規化テスト。 |
| kahoku | 実サイト確認では新しめの記事は `6月18日` のように年なし、少し古い記事は `2026年5月10日` のように年付き。記事URLには `20260608` や `20240501` のような日付が入る。 | `url_date_or_explicit_year`。表示が年なしでも、URL内 `yyyyMMdd` を優先する。URLにも年がなければ補完しない。 | URL内 `20240501` が `2024/05/01` になること、URL日付なしの `6月18日` は `NULL` になることを単体テスト。 |
| toonippo | 実取得では本日分が `14:33更新` のように時刻だけで、記事ページ `datePublished=2026-06-21T14:33:43+09:00` と一致。別日分は `M/D` 表示になるため、時刻のみは本日分と判断可能。 | `current_day_if_time_only`。時刻だけは取得日当日として補完するが、年なし `M/D` は採用しない。 | `0:39更新 -> 2026/06/20`、`6/18 23:45更新 -> NULL` をサイト別テスト。 |
| sakigake | `time[datetime]` に年付き日時。 | `machine_datetime`。属性値を優先。 | ルールサポート検査。 |
| minyu | `.status .day` に `2026/06/18 17:03`。 | `explicit_year_only`。 | 年付きスラッシュ日付の共通正規化テスト。 |
| shimotsuke | 実取得では本日分が `5:00` のように時刻だけで、記事ページ `datePublished=2026-06-21T05:00:00+09:00` と一致。別日分は `6/19 19:25` のような `M/D` 表示。page20/page33では昨年以前が `2025/9/26`、`2007/9/21` のように年付き表示。 | `current_day_or_current_year_if_yearless`。時刻だけは取得日当日、年なし `M/D` は取得年として補完し、年付き表示はその年を採用する。 | `20:30 -> 2026/06/20`、`6/18 17:03 -> 2026/06/18`、`2025/9/26 -> 2025/09/26` をサイト別テスト。 |
| jomo | `time[datetime]` に `2026-06-18 18:03`。 | `machine_datetime`。属性値を優先。 | ルールサポート検査。 |
| chibanippo | トヨタ検索では結果らしい一覧と `datetime` 付き日付を確認できたが、`日産自動車` ではフォーム送信後もページ本文に検索語が出ず、20万件超の全記事一覧に近い結果を返した。検索endpointが語によって不安定。 | 現在は `enabled: false`。キーワードで確実に絞れるendpointが確認できるまでクロール対象外。日付ルールは再有効化時に再確認する。 | 再有効化時は、検索語が結果本文または検索条件表示に反映され、無関係な全件一覧を返さないことをfixture/実ページ確認に追加する。 |
| kanaloco | カード内 `p.info` に `2026年6月18日(木) 17:03`。 | selectorを `p.info` に修正し、`explicit_year_only`。 | 保存HTMLから `p.info` の年付き日付が抽出できることをfixtureテスト。 |
| niigata_nippo | 表示は `6/18` でも `datetime` に年付き日時。 | `machine_datetime`。属性値を優先。 | ルールサポート検査。 |
| kyoto_np | 表示は `6月18日` でも `datetime` に年付き日時。 | `machine_datetime`。属性値を優先。 | ルールサポート検査。 |
| kobe_np | `2026年05月28日` のように年付き。古い記事も混在。 | `explicit_year_only`。 | 年付き日本語日付の共通正規化テスト。 |
| chugoku_np | `time[datetime]` に年付き日時。 | `machine_datetime`。属性値を優先。 | ルールサポート検査。 |
| nishinippon | `2026/06/19 08:24` のように年付き。 | `explicit_year_only`。 | 年付きスラッシュ日付の共通正規化テスト。 |
| kumamoto_nichi | カード内 `.y2024-news-list__date-wrap` に `2026年6月18日 17:21`。 | result itemを `.y2024-news-list__item` に絞り、`explicit_year_only`。 | 保存HTMLからカード内日付が抽出できることをfixtureテスト。 |
| ryukyu_shimpo | `2026/06/18` のように年付き。 | `explicit_year_only`。 | 年付きスラッシュ日付の共通正規化テスト。 |
| okinawa_times | カード内に `2026年6月18日`。 | `explicit_year_only`。 | 年付き日本語日付の共通正規化テスト。 |
| iwate_np | `8時間前` と `2026年6月17日` が混在。 | `explicit_year_only`。相対表記は採用しない。 | 相対表記は共通テストで日付化しない方針。 |
| fukui | `（2026年6月18日 午後9時07分）` のように年付き。 | `explicit_year_only`。日付部分のみ正規化。 | 年付き日本語日付の共通正規化テスト。 |
| sanyo | 実取得した検索結果では `.post_date` に `2026年6月17日 19:53` のような年付き日付。 | `explicit_year_only`。年付き日本語日付のみ採用し、年なし・時刻のみは採用しない。 | 年付き日本語日付の共通正規化と、年なし・時刻のみが `NULL` になることを検査。 |
| sanin_chuo | `time[datetime]` に年付き日時。 | `machine_datetime`。属性値を優先。 | ルールサポート検査。 |
| topics | 表示は時刻だけの場合あり、`datetime` に年付き日時。 | `machine_datetime`。表示ではなく属性値を優先。 | ルールサポート検査。 |
| kochi | `2026.06.18 17:03` のように年付きドット区切り。 | `explicit_year_only`。 | ドット区切り日付の共通正規化テスト。 |
| ehime_np | 現検索結果selectorでは掲載日なし。 | `none`。 | enabled site date_rule網羅テスト。 |
| saga_np | 表示は時刻や月日の場合あり、`datetime` に年付き日付。 | `machine_datetime`。属性値を優先。 | ルールサポート検査。 |
| nikkan_kogyo | `.ttl .date` に年付き日付想定。 | `explicit_year_only`。年なしなら次回調査でrule変更。 | 年付きスラッシュ日付の共通正規化テスト。 |
| kyodo | WordPress系の `time` / `.posted-on` 想定。 | `machine_datetime`。属性値または年付き値のみ。 | ルールサポート検査。 |
| nikkei_business | `time` / `.date` 想定。 | `machine_datetime`。年付き値のみ。 | ルールサポート検査。 |
| nikkei_xtech | `time` / `.date` 想定。 | `machine_datetime`。年付き値のみ。 | ルールサポート検査。 |
| sbbit | `.crd_ttl-pubdate` に年付き日付想定。 | `explicit_year_only`。 | 年付き日付の共通正規化テスト。 |
| nikkan_jidosha | `time` / `.date` 想定。 | `machine_datetime`。年付き値のみ。 | ルールサポート検査。 |
| denshi_device | WordPress系の `time` / `.posted-on` 想定。 | `machine_datetime`。年付き値のみ。 | ルールサポート検査。 |
| itmedia | Google CSEで独立日付なし。snippetに `2日前` と `2026/05/28` のような相対/絶対日付が混在する。 | `relative_japanese_or_explicit_year`。`.gs-snippet` を日付候補として取得し、相対日付はクロール取得時刻基準で正規化する。 | Google CSE fixtureで `2日前` と `2026/05/28` の両方を正規化できることを検査。 |
| toyokeizai | `time` / `.date` 想定。 | `machine_datetime`。年付き値のみ。 | ルールサポート検査。 |
| diamond | 正しい検索URLは `/list/search?fulltext=`。検索結果カード `.article-list-eh > a` 内の `time.published` に `2026年6月20日 6:50` のような年付き日付が表示される。 | `explicit_year_only`。年付き日本語日付のみ正規化する。 | `tests/fixtures/diamond_search_result.html` でURL・title・`time.published` の抽出と `2026/06/19` への正規化を検査。 |
| president | 検索結果カード内に信頼できる掲載日なし。 | `none`。 | enabled site date_rule網羅テスト。 |
| ryutsuu_biz | 実サイト確認では現在のselectorが広く、検索結果カードの日付表示規則を厳密に確認できていない。 | `explicit_year_only`。年なし表示は補完しない。 | 年なし月日を補完しない方針は共通テストで担保。 |
| logistics_today | `.list-heading small` に日付想定。 | `explicit_year_only`。年なしなら次回調査でrule変更。 | 年付き日付の共通正規化テスト。 |
| kentsu | 検索画面は `/articles/artcl_allartcllist` のフォーム型。`#keyword-input` に検索語を入力して送信後、検索結果カード `a[href*='/articles/artcl_rglr/']` 内の `time` に `6/18 20:37` のような年なし月日が出る。ユーザー確認では昨年以前は `yyyy/mm/dd` 形式。 | `current_year_if_yearless`。年なし `M/D HH:MM` はクロール取得時刻の年で補完し、`yyyy/mm/dd` は明示年としてそのまま正規化する。 | `tests/fixtures/kentsu_search_result.html` で年なし `6/18 20:37` と年付き `2025/12/01 09:00` の両方を検査。 |
| shokuhin_sangyo | WordPress系の `time` / `.posted-on` 想定。 | `machine_datetime`。年付き値のみ。 | ルールサポート検査。 |
| chemical_daily | WordPress系の `time` / `.posted-on` 想定。 | `machine_datetime`。年付き値のみ。 | ルールサポート検査。 |
| denki_shimbun | Google CSEスニペットに `yyyy/mm/dd` が出る結果と、日付が出ない結果が混在。記事ページは `article:published_time` / JSON-LD `datePublished`。 | `explicit_year_only`。検索結果スニペットの日付を拾い、欠けるものは記事ページfallback。 | CSE fixtureでスニペット日付、記事fixtureでmeta/JSON-LD取得を検査。 |

## 変化検知の考え方

現在のテストは三層です。

1. `tests/test_date_utils.py`
   - 明示年、年なし月日、時刻のみの正規化ルールを単体テスト。
   - タイトル中の日付を掲載日扱いしないことを検査。
   - URL内 `yyyyMMdd` を使うサイトで、URL日付を優先することを検査。
2. `tests/test_site_date_rules.py`
   - enabled siteが必ず `date_rule` を持つことを検査。
   - サイト別に年なし補完を許可したものだけが補完されることを検査。
   - `kanaloco` と `kumamoto_nichi` は保存HTML fixtureからカード内日付が取れることを検査。
3. `tests/test_parser.py` / `tests/test_crawler.py`
   - 記事ページの `article:published_time` を抽出できることを検査。
   - 検索結果で日付がないURLについて、記事ページfallbackで掲載日を補完できることを検査。
4. fixture追加時の運用
   - サイトのHTML保存がある場合は、`tests/test_site_date_rules.py` に代表HTMLから実日付を抽出するテストを追加する。
   - markup変更でselectorが外れた場合、そのサイトのfixtureテストが落ちる。
   - 表示規則が変わった場合、`date_rule` とこの資料を同時に更新する。

## 記事ページfallback

検索結果カード上の日付が `NULL` のままになる場合、crawlerは記事URLを追加取得し、以下の順で掲載日候補を探す。

1. `meta[property="article:published_time"]`
2. `meta[property="og:published_time"]`
3. `meta[name="pubdate"]`
4. `meta[name="publishdate"]`
5. `meta[name="publish_date"]`
6. `meta[name="date"]`
7. `meta[itemprop="datePublished"]`
8. `time[datetime]`
9. `[itemprop="datePublished"]`

このfallbackで使う日付は明示年付きの値だけ。記事本文やタイトルからの推測はしない。

負荷制御は `config/app.yaml` の以下で行う。

```yaml
crawler:
  article_date_lookup_enabled: true
  article_date_lookup_max_per_site: 30
  article_date_lookup_rate_limit_seconds: 1.0
```

同じURLが複数キーワードで出た場合は、同一サイトのクロール中に記事ページ日付をキャッシュし、重複取得しない。
