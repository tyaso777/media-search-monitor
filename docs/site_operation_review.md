# Site Operation Review

この資料は、サイトごとの法務・robots・掲載日取得・検索結果抽出・実装方式を横断し、最終的にクロール対象にするかを判断するための一元台帳です。

注意: この資料は法的助言ではありません。実運用前に、必要に応じて人間が規約・robots・実取得挙動を再確認します。

## 参照資料

- [site_legal_review.md](site_legal_review.md): robots、利用規約、自動取得制限、認証/CAPTCHA、本文取得有無
- [site_date_availability_review.md](site_date_availability_review.md): 検索結果画面・記事ページで掲載日を取得できるか
- [parser_strategy.md](parser_strategy.md): 検索結果部分の抽出方針
- [google_cse_strategy.md](google_cse_strategy.md): Google CSE対応方針
- [site_date_rules.md](site_date_rules.md): 掲載日抽出ルールの実装詳細
- [../config/sites.yaml](../config/sites.yaml): 実際の有効/無効設定

## 判断ルール

### 対象外

以下のいずれかに該当する場合は、原則として `対象外` とします。

- 規約上、自動取得、自動アクセス、クローリング、スクレイピング等への明示的な制限がある
- ログイン、CAPTCHA、ペイウォール、会員限定ページへのアクセスが必要
- 検索結果部分だけを安定して限定抽出できない
- 掲載日が検索結果にも記事ページにもなく、年を確定できない
- 403/429等が継続し、通常の低頻度クロールとして扱えない

### 要注意で対象候補

以下は直ちに対象外とはしませんが、運用時に注意します。

- Playwright必須
- Google CSE依存
- robots.txtで現行の検索URLが不許可、または解釈に確認が必要
- 掲載日は記事ページfallbackで取得する
- robotsまたは規約確認に曖昧さがある
- 検索結果DOMが広告、関連記事、サイドバー等と混ざりやすい

### 対象候補

以下を満たす場合に `対象候補` とします。

- robotsで検索URLが許可
- 規約上の自動取得制限が明示されていない
- ログイン/CAPTCHA不要
- 本文保存なしで目的を達成できる
- 検索結果部分を安定抽出できる
- 掲載日を年まで確定して取得できる

## AI/マイニング条項の扱い

本件はAI開発・学習目的、データマイニング、テキストマイニングを目的としません。その目的に限定された条項は、自動取得可否の直接根拠にはしません。ただし、一般的な自動取得・スクレイピング禁止条項が別にある場合は `対象外` とします。

## 最終判断表

| site_id | サイト名 | 規約上の自動取得 | robots | 日付取得 | 検索結果抽出 | 実装方式 | 最終判断 | 主な理由 | 参照 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asahi | 朝日新聞デジタル | 明示あり | 未確認 | 可 | 要注意 | Playwright | 対象外 | 規約上の自動取得制限 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| yomiuri | 読売新聞オンライン | 明示あり | 許可 | 可 | OK | httpx/CSS | 対象外 | 規約上の自動取得制限 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| mainichi | 毎日新聞 | 明示あり | 許可 | 可 | OK | httpx/CSS | 対象外 | 規約上の自動取得制限 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| sankei | 産経ニュース | 明示あり | 許可 | 可 | 要注意 | Playwright | 対象外 | 規約上の自動取得制限 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| nikkei | 日本経済新聞 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| tokyo_np | 東京新聞 | 明示未確認 | 許可 | 可 | 要注意 | Google CSE | 要注意で対象候補 | 抽出要注意 / Google CSE | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| chunichi | 中日新聞Web | 明示未確認 | 許可 | 可 | 要注意 | Google CSE | 要注意で対象候補 | 抽出要注意 / Google CSE | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| hokkaido_np | 北海道新聞デジタル | 明示未確認 | 不許可 | 可 | OK | httpx/CSS | 対象外 | robots不許可 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| kahoku | 河北新報オンライン | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| toonippo | 東奥日報 | 明示未確認 | 許可 | fallback可 | 要注意 | httpx/CSS | 要注意で対象候補 | 抽出要注意 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| sakigake | 秋田魁新報 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| yamagata_np | 山形新聞 | 明示あり | 許可 | 未確認 | 未確認 | 未確認 | 対象外 | 規約上の自動取得制限 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| minyu | 福島民友新聞 | 明示未確認 | 許可 | 可 | 要注意 | httpx/CSS | 要注意で対象候補 | 抽出要注意 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| shimotsuke | 下野新聞 SOON | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| jomo | 上毛新聞 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| chibanippo | 千葉日報 | 明示あり | 許可 | 不可 | 不可 | Playwright | 対象外 | 規約上の自動取得制限 / 日付/検索結果抽出不可 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| kanaloco | カナロコ 神奈川新聞 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| niigata_nippo | 新潟日報デジタルプラス | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| shinmai | 信濃毎日新聞デジタル | 明示あり | 許可 | 未確認 | 未確認 | 未確認 | 対象外 | 規約上の自動取得制限 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| shizushin | 静岡新聞 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| kyoto_np | 京都新聞 | 明示未確認 | 不許可 | 可 | OK | httpx/CSS | 対象外 | robots不許可 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| kobe_np | 神戸新聞NEXT | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| chugoku_np | 中国新聞デジタル | 明示未確認（AI/マイニング条項除外） | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| shikoku_np | 四国新聞 | 明示未確認 | 許可 | 未確認 | 未確認 | 未確認 | 要注意で対象候補 | 日付未確認 / 抽出要注意 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| nishinippon | 西日本新聞me | 明示未確認 | 許可 | 可 | 要注意 | Playwright | 要注意で対象候補 | 抽出要注意 / Playwright | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| kumamoto_nichi | 熊本日日新聞 | 明示未確認（AI/マイニング条項除外） | 許可 | 可 | 要注意 | Playwright | 要注意で対象候補 | 抽出要注意 / Playwright | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| ryukyu_shimpo | 琉球新報 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| okinawa_times | 沖縄タイムス | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| iwate_np | 岩手日報 | 明示あり | 不許可 | 可 | 要注意 | httpx/CSS | 対象外 | 規約上の自動取得制限 / robots不許可 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| fukui | 福井新聞 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| sanyo | 山陽新聞 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| sanin_chuo | 山陰中央新報 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| topics | 徳島新聞 | 明示あり | 許可 | 可 | OK | httpx/CSS | 対象外 | 規約上の自動取得制限 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| kochi | 高知新聞 | 明示未確認（AI/マイニング条項除外） | 不許可 | 可 | OK | httpx/CSS | 対象外 | robots不許可 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| ehime_np | 愛媛新聞 | 明示未確認 | 許可 | 可 | 要注意 | Playwright | 要注意で対象候補 | 抽出要注意 / Playwright | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| saga_np | 佐賀新聞 | 明示未確認 | 不許可 | 可 | OK | httpx/CSS | 対象外 | robots不許可 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| nikkan_kogyo | 日刊工業新聞 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| kyodo | 共同通信 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| nikkei_business | 日経ビジネス | 明示未確認（AI/マイニング条項除外） | 許可 | 可 | 要注意 | Playwright | 要注意で対象候補 | 抽出要注意 / Playwright | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| nikkei_xtech | 日経クロステック | 明示未確認（AI/マイニング条項除外） | 許可 | 可 | 要注意 | Playwright | 要注意で対象候補 | 抽出要注意 / Playwright | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| sbbit | ビジネス+IT | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| jiji | 時事ドットコム | 明示未確認 | 許可 | 可 | 要注意 | Google CSE | 要注意で対象候補 | 抽出要注意 / Google CSE | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| nikkan_jidosha | 日刊自動車新聞 電子版 | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| denshi_device | 電波新聞デジタル | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| itmedia | ITmedia | 明示未確認 | 不許可 | 可 | 要注意 | Google CSE | 対象外 | robots不許可 / Google CSE直接取得 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| impress_watch | Impress Watch | 明示未確認 | 許可 | 可 | 要注意 | Google CSE | 要注意で対象候補 | 抽出要注意 / Google CSE | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| toyokeizai | 東洋経済オンライン | 明示未確認 | 不許可 | 可 | OK | httpx/CSS | 対象外 | robots不許可 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| diamond | ダイヤモンド・オンライン | 明示あり | 許可 | 可 | OK | httpx/CSS | 対象外 | 規約上の自動取得制限 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| president | PRESIDENT Online | 明示未確認 | 許可 | 可 | 要注意 | httpx/CSS | 要注意で対象候補 | 抽出要注意 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| ryutsuu_biz | 流通ニュース | 明示未確認 | 許可 | fallback可 | 要注意 | httpx/CSS | 要注意で対象候補 | 抽出要注意 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| logistics_today | LOGISTICS TODAY | 明示未確認 | 許可 | 可 | OK | httpx/CSS | 対象候補 |  | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| kentsu | 建通新聞 | 明示未確認 | 許可 | 可 | 要注意 | Playwright | 要注意で対象候補 | 抽出要注意 / Playwright | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| shokuhin_sangyo | 食品産業新聞社ニュースWEB | PDF未確認 | 許可 | 可 | OK | httpx/CSS | 要注意で対象候補 | 規約PDF未確認 | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |
| denki_shimbun | 電気新聞ウェブサイト | 明示未確認 | 許可 | fallback可 | 要注意 | Google CSE | 要注意で対象候補 | 抽出要注意 / Google CSE | [legal](site_legal_review.md) / [date](site_date_availability_review.md) |

## 運用反映

- この資料の `最終判断` は判断台帳であり、実際のクロール有効/無効は [../config/sites.yaml](../config/sites.yaml) に反映する。
- 既存DBに反映する場合は、`import-config` で再取り込みするか、DBの `sites.enabled` を更新する。
- 判断を変更した場合は、根拠資料である `site_legal_review.md` または `site_date_availability_review.md` も同時に更新する。
