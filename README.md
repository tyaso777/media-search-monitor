# News Monitor

SQLiteに新聞社・業界メディア等の検索結果URLを蓄積し、会社・トピック別に確認するためのツールです。

GitHubから取得後の必要ソフトウェア、ビルド方法、Playwright有無別クロール、検索ワード更新方法は以下にまとめています。

```text
docs/setup_and_operation.md
```

主な構成は3つです。

- Python crawler: サイト検索結果を取得して `data/news_monitor.sqlite` に保存
- Tauri viewer: SQLiteを読み、検索結果・キーワード・要望・サイト状態を表示するWindows向けUI
- Localhost viewer: Rust exeがlocalhostサーバーを起動し、既定ブラウザで同じUIを表示

記事本文取得、ログイン突破、CAPTCHA回避、通知、スケジューラは範囲外です。

## 利用者向け

ビルド済みexeでDBを見るだけなら、追加の開発環境は不要です。Tauri/WebView2やnpmを使わない環境では、`news-monitor-local-viewer.exe` を使ってください。既定ブラウザで画面を開きます。

必要なもの:

- `news-monitor-viewer.exe` または `news-monitor-local-viewer.exe`
- `data/news_monitor.sqlite`

実行ファイルの生成先:

```text
src-tauri/target/release/news-monitor-viewer.exe
local-viewer/target/release/news-monitor-local-viewer.exe
```

Viewerでは以下ができます。

- 会社・トピック別の検索結果表示
- 掲載日Min・ヒット日Minによる優先度確認
- 会社/トピック内の記事ソート: 掲載日順、ヒット日順、サイト順
- 候補キーワードでの記事絞り込み
- 掲載日直近N日分の記事をMarkdownでコピー
- キーワード一覧の閲覧
- サイト追加要望、キーワード追加/削除要望の登録
- 管理画面での要望ステータス・実装者コメント管理
- 管理画面でのサイト状態確認

## クロール環境

クロールを実行するPCにはPython環境が必要です。プロジェクトでは `uv` を使います。

```powershell
uv sync --extra test --extra playwright
```

Playwright対象サイトも取る場合は、初回だけChromiumを入れます。

```powershell
uv run playwright install chromium
```

Playwrightを使わないHTTP/Google CSE対象サイトだけならChromiumは不要です。ただし全サイトを対象にする運用では `--enable-playwright` とChromiumを用意してください。

## DB初期化・設定import

```powershell
uv run news-monitor init-db --db data/news_monitor.sqlite
uv run news-monitor import-config `
  --db data/news_monitor.sqlite `
  --app-config config/app.yaml `
  --keywords config/keywords.csv `
  --sites config/sites.yaml
```

既存DBを作り直す場合は、削除ではなく退避してから作成してください。

```powershell
if (Test-Path data/news_monitor.sqlite) {
  Move-Item data/news_monitor.sqlite "data/news_monitor_$(Get-Date -Format yyyyMMdd_HHmmss).sqlite.bak"
}
uv run news-monitor init-db --db data/news_monitor.sqlite
uv run news-monitor import-config --db data/news_monitor.sqlite --app-config config/app.yaml --keywords config/keywords.csv --sites config/sites.yaml
```

## クロール

### 全サイト取得 Playwrightあり

Playwright対象サイトも含めて取得する通常運用です。初回のみChromiumをインストールしてください。

```powershell
uv run playwright install chromium
```

```powershell
uv run news-monitor crawl-and-report `
  --db data/news_monitor.sqlite `
  --app-config config/app.yaml `
  --date 2026-06-21 `
  --enable-playwright `
  --max-concurrent-sites 8 `
  --max-concurrent-playwright-sites 1
```

### Playwrightなし

Chromiumを使わず、HTTP/Google CSEで取得できるサイトだけを対象にします。Playwright必須サイトはスキップされます。

```powershell
uv run news-monitor crawl-and-report `
  --db data/news_monitor.sqlite `
  --app-config config/app.yaml `
  --date 2026-06-21 `
  --max-concurrent-sites 8
```

### レポートHTMLだけ再生成

クロールせず、既存DBからHTMLレポートだけ再生成する場合:

```powershell
uv run news-monitor report --db data/news_monitor.sqlite --date 2026-06-21 --output-dir outputs
```

Viewerの会社/トピック一覧を高速に表示するため、クロール後はDB内の表示用集計キャッシュも更新されます。既存DBに対して手動で再作成する場合:

```powershell
uv run news-monitor rebuild-viewer-cache --db data/news_monitor.sqlite
```

このキャッシュには記事一覧の表示用行も含まれます。Viewerは各会社/トピックを開いた時に初回100件を読み込み、必要に応じて100件ずつ追加表示します。

`crawl` と `crawl-and-report` は以下の絞り込みもできます。

- `--site-id`
- `--candidate-keyword-id`
- `--max-sites`
- `--max-keywords`

## クロールマナーと並列実行

Crawlerは同一サイト内では逐次実行し、サイトごとの `rate_limit_seconds` を待ちます。複数サイトは並列実行できます。

SQLiteはWAL、`busy_timeout`、短時間リトライでロック衝突を軽減します。

## キーワード管理

`config/keywords.csv` は親キーワードと候補キーワードを管理します。

列:

```csv
base_keyword_id,base_keyword,group_type,candidate_keyword_id,candidate_keyword,enabled,notes
```

`group_type`:

- `company`: 会社名
- `topic`: トピック

ID列は空欄で構いません。import時に安定したUUID系IDが内部生成されます。旧形式の `b001` / `c001` はimport時の移行用エイリアスとして扱われます。

例:

```csv
,トヨタ自動車,company,,トヨタ,1,
,生成AI,topic,,LLM,1,
```

ユーザー向けUIではキーワードを直接編集せず、追加・削除要望を登録します。直接編集は管理画面またはCSVで行います。

## サイト設定

サイト定義は主に以下で管理します。

- `config/sites.yaml`: 基本サイト定義
- `config/site_overrides.yaml`: selectorやfetch strategyの上書き
- `config/date_rules.yaml`: 掲載日正規化ルール

fetch strategy:

- `httpx`: 静的HTML取得
- `truststore`: OS証明書ストアを使ったHTTPS証明書検証
- `google_cse`: Google CSEの内部リクエストをHTTPで取得
- `playwright`: JavaScript描画後のHTMLを取得
- `playwright_form`: Playwrightでフォーム送信して取得

Playwright依存削減の調査メモ:

```text
docs/playwright_reduction_audit.md
```

## サイト状態検知

クロール時の問題はDBに記録されます。

- `fetch_errors`: 取得・パース・通信エラー
- `crawl_skips`: スキップ理由
- `search_result_items`: 取得済みURL、掲載日欠落
- `search_result_hits`: キーワード別ヒット

Tauri viewerの管理画面ではサイト別に以下を表示します。

- 最新runのヒット件数
- 最新runのエラー件数
- 総記事件数
- 掲載日欠落件数
- 最新エラー内容
- 最新スキップ理由
- HTTP / Playwright の区別

サイト側のHTML構造変更でselectorが壊れた場合は、典型的には `エラーあり` または `最新run 0件` として検知します。

## 開発・ビルド環境

ビルド済みexeを使うだけならNode.js/npm/Rustは不要です。

このプロジェクトには、閲覧UIのexeが2種類あります。

| 種類 | 用途 | ビルドに必要なもの | 利用者側の動き |
|---|---|---|---|
| Tauri版 | 通常のWindowsデスクトップアプリとして配布したい場合 | Node.js/npm、Rust/Cargo、Tauri Windowsビルド依存 | exeを起動するとアプリ画面が開く |
| localhost版 | Node.js/npmやTauriを使わずにビルドしたい場合 | Rust/Cargoのみ | exeを起動するとlocalhostサーバーが立ち上がり、既定ブラウザで画面が開く |

### Tauri版をビルドする場合

Tauri版は `src-tauri/` と `ui/` を使って、Windowsアプリを生成します。ビルドする環境には以下が必要です。

- Node.js / npm
- Rust / Cargo
- TauriのWindowsビルド依存
- WebView2 Runtime 通常はWindowsに同梱

依存インストールはプロジェクトルートで実行します。

```powershell
npm install
```

ビルド:

```powershell
npm.cmd run build
```

生成物:

```text
src-tauri/target/release/news-monitor-viewer.exe
src-tauri/target/release/bundle/nsis/News Monitor Viewer_0.1.0_x64-setup.exe
src-tauri/target/release/bundle/msi/News Monitor Viewer_0.1.0_x64_en-US.msi
```

### localhost版をビルドする場合

localhost版は `local-viewer/` と `ui/` を使って、既定ブラウザで開く軽量exeを生成します。Node.js/npmは不要です。ビルドする環境には以下だけ必要です。

- Rust / Cargo

ビルド:

```powershell
cd local-viewer
cargo build --release
```

生成物:

```text
local-viewer/target/release/news-monitor-local-viewer.exe
```

プロジェクトルートから起動する場合:

```powershell
.\local-viewer\target\release\news-monitor-local-viewer.exe
```

起動すると `127.0.0.1` の空きポートでサーバーを立ち上げ、既定ブラウザを開きます。右上の `終了` ボタンでlocalhostサーバーを停止できます。

ブラウザを自動で開かない確認用途では以下も使えます。

```powershell
.\local-viewer\target\release\news-monitor-local-viewer.exe --no-open --port 8765
```

GitHubにはコードと設定を置き、GitHub Actionsまたはビルド用PCでexeを作成する運用が現実的です。閲覧だけの環境にnpm/Rustを入れず、ビルド済みexeを使う形にできます。

## テスト

```powershell
uv run pytest
node --check ui/app.js
node --check ui/api.js
cargo test --manifest-path src-tauri/Cargo.toml
cargo check --manifest-path local-viewer/Cargo.toml
```

## ドキュメント

資料の全体像は [docs/README.md](docs/README.md) に整理しています。

Markdown資料をHTML化する場合:

```powershell
uv run python scripts/render_markdown_html.py docs/site_date_availability_review.md
```

主要な入口:

| 目的 | 資料 |
|---|---|
| docs全体の索引 | [docs/README.md](docs/README.md) |
| セットアップ、ビルド、クロール、検索ワード更新 | [docs/setup_and_operation.md](docs/setup_and_operation.md) |
| サイト別の掲載日取得可否 | [docs/site_date_availability_review.md](docs/site_date_availability_review.md) |
| 掲載日取得ルールの詳細 | [docs/site_date_rules.md](docs/site_date_rules.md) |

## Git管理方針

Gitに入れるもの:

- `src/`
- `src-tauri/src/`
- `ui/`
- `config/`
- `docs/`
- `tests/`
- `scripts/`
- `README.md`
- `pyproject.toml`
- `uv.lock`
- `package.json`
- `package-lock.json`
- `src-tauri/Cargo.toml`
- `src-tauri/Cargo.lock`

Gitに入れないもの:

- `.venv/`
- `node_modules/`
- `src-tauri/target/`
- `data/*.sqlite`
- `reports/`
- `outputs/`
- Playwrightのブラウザ本体
