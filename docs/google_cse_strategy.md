# Google CSE対応方針

## 概要

東京新聞、中日新聞、ITmedia は Google Custom Search Engine を使った検索結果を表示する。

ブラウザでは以下の流れで結果が表示される。

1. サイトの検索ページHTMLを取得する。
2. `cse.google.com/cse.js?cx=...` が読み込まれる。
3. `cse.js` 内の短命 `cse_token` と `cselibVersion` を使って、Google CSE element API へ追加リクエストが発生する。
4. JavaScriptが `.gsc-webResult.gsc-result` などの検索結果DOMを差し込む。

## 実装状態

東京新聞、中日新聞、ITmedia は `fetch_strategy: google_cse` に切替済み。

`GoogleCseFetcher` は以下を行う。

1. `https://cse.google.com/cse.js?cx={cx}` を取得する。
2. `cse_token`, `cselibVersion`, `exp`, `fexp` を抽出する。
3. `https://cse.google.com/cse/element/v1?...` を取得する。
4. JSONPレスポンスの `results[]` から `titleNoFormatting`, `unescapedUrl`, `contentNoFormatting` を読む。
5. 既存CSS parserが読める `.gsc-webResult.gsc-result` 風HTMLへ変換する。

ITmediaは検索結果snippetに `2日前` のような相対日付と `2026/05/28` のような明示年付き日付が混在する。現実装では明示年付きsnippetのみ検索結果側で正規化し、相対日付は記事ページfallback対象にする。

## 設定項目

| 項目 | 意味 |
|---|---|
| `fetch_strategy` | 実際に使う取得方式。`httpx`, `playwright`, `google_cse` を許容。 |
| `google_cse_lightweight_candidate` | Google CSE直接取得へ置換できる可能性があるサイト。 |
| `google_cse_cx` | Google CSE `cx`。 |
| `google_cse_sort` | Google CSE `sort`。東京新聞は `date`、中日新聞・ITmediaは未指定。 |
| `google_cse_notes` | 軽量化時の注意点。 |

## 切替条件

新しいサイトを `google_cse` へ切り替えるのは、次が確認できてからにする。

- `cse.js?cx=...` から `cse_token` と `cselibVersion` を取得できる。
- `element/v1` のJSONPレスポンスからタイトル、URL、スニペット、掲載日相当文字列を安定抽出できる。
- Google CSEの結果が検索結果本体であり、サイドバーや広告ではない。
- レート制限や利用条件に反しない。
- fixtureベースのテストでレスポンス形式変化を検知できる。

`cse_token` は固定値として保存しない。毎回 `cse.js` から取得する。
