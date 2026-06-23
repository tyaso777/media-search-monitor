# パーサ戦略

このプロジェクトでは、サイトごとのHTML差分をすべてPythonコードへ直書きせず、まずCSS selector設定で吸収する。
ただし、CSS selectorだけでは安全に表現できないサイトに備えて、設定上で戦略を明示する。

## parser_strategy

| 値 | 意味 | 実装状況 |
|---|---|---|
| `css_selectors` | `result_item_selector`、`title_selector`、`url_selector`、`date_selector`、`snippet_selector` で検索結果カードを読む。 | 実装済み。標準。 |
| `site_specific` | サイト専用のPythonパーサで読む。 | 差し込み口のみ実装済み。未登録サイトで指定すると明示的にエラー。 |

初期方針として、HTML構造が安定していて検索結果カード内にタイトル・URL・掲載日が分かれているサイトは `css_selectors` を使う。
検索結果が特殊な構造、複数カード種別混在、タイトル末尾日付、または記事ページ側の独自日付要素が必要な場合は `site_specific` を検討する。

## date_strategy

| 値 | 意味 |
|---|---|
| `css_selector` | 検索結果カード内の `date_selector` から掲載日候補を取る。 |
| `article_page_fallback` | 検索結果で取れない場合、記事ページのmeta / timeから補完する。 |
| `title_trailing_date` | サイト別に確認済みの場合だけ、タイトル末尾の日付を掲載日候補として切り出す。 |
| `site_specific` | サイト専用ロジックで掲載日候補を取る。 |
| `none` | 検索結果カードから掲載日を取らない。 |

`date_strategy` は日付候補の取得元を示す。取得した文字列を `yyyy/mm/dd` に正規化するルールは、従来通り `date_rule` が担当する。

## 現状の重要例

| site_id | 方針 |
|---|---|
| `nikkei` | `css_selectors` + `css_selector`。検索結果カードの `.nui-card__meta-pubdate` が掲載日。タイトルとは別要素。 |
| `jomo` | 監査上、タイトル末尾日付の候補。ただし実装前に専用fixtureで確認する。 |
| `shimotsuke` | 記事ページではタイトル直下に `M/D HH:MM` があるケースを確認。検索結果または記事ページの専用要素を使うべきで、タイトル本文の日付は使わない。 |
| `itmedia` | Google CSEで検索結果に専用日付selectorなし。snippet利用は慎重に扱う。 |

## 実装上の約束

- タイトル本文やカード全体テキストから無条件に日付を拾わない。
- サイト別に確認できた場合だけ、`title_trailing_date` や `site_specific` を使う。
- `site_specific` を設定してPythonパーサが未登録の場合は、無音で失敗せず `NotImplementedError` にする。
- HTML構造変更に気づけるよう、サイト別fixtureテストを追加してから設定を変更する。
