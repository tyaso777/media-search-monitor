# Setup and Operation Guide

この資料は、GitHubからこのプロジェクトを取得した後に必要なソフトウェア、ビルド方法、クロール方法、検索ワード更新方法をまとめたものです。

## 1. 必要なソフトウェア

用途によって必要なものが変わります。

### DBを見るだけの利用者

ビルド済みexeとSQLite DBを見るだけなら、開発用ソフトウェアは不要です。

必要:

- `news-monitor-viewer.exe` または `news-monitor-local-viewer.exe`
- `data/news_monitor.sqlite`

不要:

- Python
- uv
- Node.js / npm
- Rust / Cargo
- Playwright Chromium

Tauri版ではなく `news-monitor-local-viewer.exe` を使う場合、画面は利用者PCの既定ブラウザで開きます。利用者側にNode.js/npmやRustは不要です。

### クロール実行者

Webクロールを実行してDBを更新するPCでは、Python環境が必要です。

必要:

- Git
- uv
- Python 3.11以上
- Python依存パッケージ
- Playwright対象サイトも取る場合はChromium

セットアップ:

```powershell
git clone <repository-url>
cd <repository-directory>
uv sync --extra test --extra playwright
```

Playwright版クロールも使う場合は、初回だけChromiumを入れます。

```powershell
uv run playwright install chromium
```

### exeビルド担当者

閲覧UIのexeには2種類あります。どちらをビルドするかで必要なソフトウェアが変わります。

| 種類 | 用途 | ビルドに必要なもの | 生成物 |
|---|---|---|---|
| Tauri版 | 通常のWindowsデスクトップアプリとして配布したい場合 | Git、Node.js/npm、Rust/Cargo、Tauri Windowsビルド依存 | `news-monitor-viewer.exe`、MSI/NSIS installer |
| localhost版 | 会社環境でNode.js/npmやTauriを避けたい場合 | Git、Rust/Cargo | `news-monitor-local-viewer.exe` |

Tauri版のWindows exeをビルドするPCでは、Node.js/npmとRustが必要です。

必要:

- Git
- Node.js / npm
- Rust / Cargo
- Windows WebView2 Runtime 通常はWindowsに同梱

ビルドだけならPythonは必須ではありません。ただし、クロールやPythonテストも確認するならPython/uvも必要です。

localhost + 既定ブラウザ版だけをビルドする場合は、Node.js/npmは不要です。Rust/Cargoだけでビルドできます。

## 2. Build方法

### Tauri版

Tauri版は `src-tauri/` と `ui/` を使ってWindowsアプリを生成します。インストーラーも作る配布向けの方式です。

GitHubから取得後、プロジェクトルートでNode依存を入れます。

```powershell
npm install
```

exeをビルドします。

```powershell
npm.cmd run build
```

生成物:

```text
src-tauri/target/release/news-monitor-viewer.exe
src-tauri/target/release/bundle/nsis/News Monitor Viewer_0.1.0_x64-setup.exe
src-tauri/target/release/bundle/msi/News Monitor Viewer_0.1.0_x64_en-US.msi
```

開発中にTauriを起動する場合:

```powershell
npm.cmd run dev
```

注意:

- `news-monitor-viewer.exe` を起動中だと、`npm.cmd run build` がexeを上書きできず失敗します。
- ビルド前に起動中のviewerを閉じてください。

### localhost + 既定ブラウザ版

会社環境でNode.js/npmやTauriの扱いが難しい場合はこちらを使います。UI本体は `ui/` を共通利用し、Rust exeがlocalhost APIを提供します。

この方式ではNode.js/npmは不要です。

```powershell
cd local-viewer
cargo build --release
```

生成物:

```text
local-viewer/target/release/news-monitor-local-viewer.exe
```

起動:

```powershell
local-viewer/target/release/news-monitor-local-viewer.exe
```

起動すると、空きポートの `http://127.0.0.1:xxxxx/` を立ち上げ、既定ブラウザを自動で開きます。
右上の `終了` ボタンでlocalhostサーバーを停止できます。その後、ブラウザのタブを閉じてください。

確認・開発用にブラウザ自動起動を止める場合:

```powershell
local-viewer/target/release/news-monitor-local-viewer.exe --no-open --port 8765
```

DB探索順はTauri版と同様です。通常はプロジェクト直下の以下を読みます。

```text
data/news_monitor.sqlite
```

別DBを指定する場合は環境変数を使います。

```powershell
$env:NEWS_MONITOR_DB='C:\path\to\news_monitor.sqlite'
local-viewer/target/release/news-monitor-local-viewer.exe
```

## 3. DB初期化と設定import

初回、またはDBを作り直す場合:

```powershell
uv run news-monitor init-db --db data/news_monitor.sqlite
uv run news-monitor import-config `
  --db data/news_monitor.sqlite `
  --app-config config/app.yaml `
  --keywords config/keywords.csv `
  --sites config/sites.yaml
```

既存DBを残して作り直す場合:

```powershell
if (Test-Path data/news_monitor.sqlite) {
  Move-Item data/news_monitor.sqlite "data/news_monitor_$(Get-Date -Format yyyyMMdd_HHmmss).sqlite.bak"
}

uv run news-monitor init-db --db data/news_monitor.sqlite
uv run news-monitor import-config `
  --db data/news_monitor.sqlite `
  --app-config config/app.yaml `
  --keywords config/keywords.csv `
  --sites config/sites.yaml
```

設定ファイルだけ更新した場合は、DBを消さずに `import-config` を再実行します。

```powershell
uv run news-monitor import-config `
  --db data/news_monitor.sqlite `
  --app-config config/app.yaml `
  --keywords config/keywords.csv `
  --sites config/sites.yaml
```

## 4. Webクロール方法

### Playwrightを使う版

全サイトを対象にする通常運用はこちらです。

初回だけ:

```powershell
uv run playwright install chromium
```

クロール:

```powershell
uv run news-monitor crawl-and-report `
  --db data/news_monitor.sqlite `
  --app-config config/app.yaml `
  --date 2026-06-22 `
  --enable-playwright `
  --max-concurrent-sites 8 `
  --max-concurrent-playwright-sites 1
```

`--enable-playwright` を付けると、Playwright対象サイトも取得します。

### Playwrightを使わない版

Chromiumを入れない環境、または軽量確認用です。Playwright必須サイトはスキップされます。

```powershell
uv run news-monitor crawl-and-report `
  --db data/news_monitor.sqlite `
  --app-config config/app.yaml `
  --date 2026-06-22 `
  --max-concurrent-sites 8
```

この場合、`fetch_strategy: httpx` と `fetch_strategy: google_cse` のサイトは取得対象になります。

### レポートだけ再生成

クロールせず、既存DBからHTMLレポートだけ再生成する場合:

```powershell
uv run news-monitor report `
  --db data/news_monitor.sqlite `
  --date 2026-06-22 `
  --output-dir outputs
```

## 5. 検索ワードのアップデート方法

検索ワードは `config/keywords.csv` で管理します。

列:

```csv
base_keyword_id,base_keyword,group_type,candidate_keyword_id,candidate_keyword,enabled,notes
```

意味:

- `base_keyword_id`: 空欄でよい。import時に内部IDを生成
- `base_keyword`: 親キーワード。例: `トヨタ自動車`, `生成AI`
- `group_type`: `company` または `topic`
- `candidate_keyword_id`: 空欄でよい。import時に内部IDを生成
- `candidate_keyword`: 実際に検索する候補キーワード
- `enabled`: `1` なら有効、`0` なら無効
- `notes`: メモ

会社の例:

```csv
,トヨタ自動車,company,,トヨタ,1,
,トヨタ自動車,company,,TOYOTA,1,
```

トピックの例:

```csv
,生成AI,topic,,生成AI,1,
,生成AI,topic,,LLM,1,
,生成AI,topic,,大規模言語モデル,1,
```

CSVを変更した後は、DBへ反映します。

```powershell
uv run news-monitor import-config `
  --db data/news_monitor.sqlite `
  --app-config config/app.yaml `
  --keywords config/keywords.csv `
  --sites config/sites.yaml
```

その後、次回クロールから新しい検索ワードが使われます。

## 6. UIからのキーワード要望

通常ユーザーは直接キーワードを編集せず、Tauri viewerの `要望` タブから追加・削除希望を登録できます。

管理者は `管理` タブで以下を確認・更新できます。

- キーワード追加/削除要望
- サイト追加要望
- ステータス
- 実装者コメント

ただし、要望を登録しただけではクロール対象にはなりません。実際に検索対象へ反映するには、管理者がCSVまたは管理UIでキーワードを追加し、必要に応じて `import-config` を実行してください。

## 7. 確認コマンド

Pythonテスト:

```powershell
uv run pytest
```

UI JavaScript構文チェック:

```powershell
node --check ui/app.js
```

Rust/Tauri側テスト:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml
```
