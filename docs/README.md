# Documentation Index

このディレクトリには、運用手順、サイト調査、実装方針、監査メモを置いています。
通常参照する正式資料と、過去の調査過程を残すための監査メモを分けています。

## まず読む資料

| 資料 | 何が書いてあるか |
|---|---|
| [setup_and_operation.md](setup_and_operation.md) | GitHubから取得後に必要なソフトウェア、Tauri版/localhost版のビルド方法、DB初期化、Playwright有無別クロール、検索ワード更新方法 |
| [../README.md](../README.md) | プロジェクト全体の概要、主要コマンド、Git管理方針 |

## 掲載日取得まわり

| 資料 | 何が書いてあるか |
|---|---|
| [site_date_availability_review.md](site_date_availability_review.md) | 各サイトについて、検索結果画面で掲載日が取れるか、記事ページfallbackが必要か、相対日付があるか等をまとめた主レビュー表 |
| [site_date_availability_review.html](site_date_availability_review.html) | 上記レビュー表のHTML版。ブラウザで確認しやすい版 |
| [site_date_rules.md](site_date_rules.md) | サイトごとの掲載日抽出ルール。どのselector/ルールで日付を解釈するか |

掲載日ルールを確認したい場合は、まず [site_date_availability_review.md](site_date_availability_review.md) を見て、実装ルールの詳細は [site_date_rules.md](site_date_rules.md) を見ます。

## クロール・パーサ実装方針

| 資料 | 何が書いてあるか |
|---|---|
| [parser_strategy.md](parser_strategy.md) | 検索結果パーサの設計方針。CSS selector中心、サイト別parserが必要な場合の考え方 |
| [google_cse_strategy.md](google_cse_strategy.md) | Google CSEをPlaywrightなしで直接HTTP取得する方針・実装メモ |
| [playwright_reduction_audit.md](playwright_reduction_audit.md) | Playwright依存サイトをHTTP化できるか調査したメモ。HTTP化できたサイト・維持するサイトの判断 |

サイト設定や取得方式を変える場合は、この3つを確認します。

## 対象メディア

| 資料 | 何が書いてあるか |
|---|---|
| [site_operation_review.md](site_operation_review.md) | 法務・robots・掲載日取得・検索結果抽出・実装方式を横断して、最終的にクロール対象にするかを判断する一元台帳 |
| [site_legal_review.md](site_legal_review.md) | サイト別のrobots.txt、規約確認、認証/CAPTCHA/本文取得有無、運用判断ステータスを記録する法務・運用レビュー台帳 |
| [site_notes/initial_media_targets.md](site_notes/initial_media_targets.md) | 初期対象メディアの考え方・候補整理 |

## 過去調査メモ

正式資料に反映済み、または調査過程を残す目的の資料は [archive/](archive/) に置いています。

| 資料 | 何が書いてあるか |
|---|---|
| [archive/site_date_availability_matrix.md](archive/site_date_availability_matrix.md) | 掲載日取得可否の機械監査寄り一覧。主資料は `site_date_availability_review.md` |
| [archive/site_date_location_audit.md](archive/site_date_location_audit.md) | 各サイトで掲載日がHTML上のどこに出ているかを調べた監査メモ |
| [archive/title_trailing_date_audit.md](archive/title_trailing_date_audit.md) | タイトル末尾に日付が出るパターンを調べた監査メモ |
| [archive/assumptions.md](archive/assumptions.md) | 初期実装時の前提メモ。現行ルールはREADMEとsetup資料を参照 |

## どれを見ればよいか

| 目的 | 見る資料 |
|---|---|
| セットアップ、ビルド、クロール方法を知りたい | [setup_and_operation.md](setup_and_operation.md) |
| Playwrightあり/なしのクロールコマンドを知りたい | [setup_and_operation.md](setup_and_operation.md) |
| localhost版のビルド方法を知りたい | [setup_and_operation.md](setup_and_operation.md) |
| 各サイトの日付取得可否を確認したい | [site_date_availability_review.md](site_date_availability_review.md) |
| 日付抽出ロジックの実装意図を確認したい | [site_date_rules.md](site_date_rules.md) |
| サイト別selectorやパーサ方針を見たい | [parser_strategy.md](parser_strategy.md) |
| Google CSE対応方針を見たい | [google_cse_strategy.md](google_cse_strategy.md) |
| Playwright依存を減らせるかの調査を見たい | [playwright_reduction_audit.md](playwright_reduction_audit.md) |
| 最終的にサイトをクロール対象にするか確認したい | [site_operation_review.md](site_operation_review.md) |
| サイト別のrobots・規約確認状況を見たい | [site_legal_review.md](site_legal_review.md) |
