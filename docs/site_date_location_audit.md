# 掲載日箇所 監査メモ

- 監査クエリ: `トヨタ`
- 静的HTTP取得ベース。Playwright必須サイトは追加確認が必要。

| site_id | サイト | PW | status/items | date_selector | 判定 | 取得日付例 | タイトル日付 | メモ |
|---|---|---:|---:|---|---|---|---:|---|
| asahi | 朝日新聞デジタル | Y | 200/0 | `time, .date, .Date` | 未確認（検索結果カードなし） |  |  |  |
| yomiuri | 読売新聞オンライン |  | 200/20 | `.c-list-date` | 掲載日専用らしき要素 | 2026/06/20 15:35 |  | ［試乗記］野外楽しいＥＶに…トヨタ　ｂＺ４Ｘツーリング 2026/06/20 15:35 #＠ＣＡＲＳニュース |
| mainichi | 毎日新聞 |  | 200/20 | `.articletag-date` | 掲載日専用らしき要素 | 2026/6/21 05:01 |  | 第９７回都市対抗野球 東北2次予選　エフコム、本大会逃す　TDKにコールド負け　／福島 2026/6/21 05:01 798文字 第97回都市対抗野球大会（日本野球連盟、毎日新聞社主催）の東北2次予 |
| sankei | 産経ニュース |  | 200/106 | `time, .date` | date_selectorで日付取得できず |  |  | トップ |
| nikkei | 日本経済新聞 |  | 200/10 | `.nui-card__meta-pubdate` | 掲載日専用らしき要素 | 2026年6月21日 05時00分 |  | 誰でも参加OKの朝活、個人で続けまちを元気に　井上・山形市副市長 日経MJ 山形 大阪 鹿児島 愛媛 東北 関西 九州・沖縄 四国 2026年6月21日 05時00分 ...JR九州赤間駅長だった出田 |
| tokyo_np | 東京新聞 |  | 200/83 | `time, .date` | date_selectorで日付取得できず |  |  | #本音のコラム |
| chunichi | 中日新聞Web |  | 200/109 | `time, .date` | date_selectorで日付取得できず |  |  | 解く、ひらめく　脳活 |
| hokkaido_np | 北海道新聞デジタル |  | 200/135 | `time, .date` | date_selectorで日付取得できず |  |  | 石狩 |
| kahoku | 河北新報オンライン |  | 200/196 | `time, .date` | date_selectorで日付取得できず |  |  | 朝刊・夕刊 記事一覧 紙面ビューアー |
| toonippo | 東奥日報 |  | 200/278 | `time, .date` | date_selectorで日付取得できず |  |  | ニュース |
| sakigake | 秋田魁新報 |  | 200/83 | `time, .date` | date_selectorで日付取得できず |  |  | 秋田のニュース |
| yamagata_np | 山形新聞 |  | 404/0 | `time, .date` | 未確認（検索結果カードなし） |  |  |  |
| minyu | 福島民友新聞 |  | 200/170 | `time, .date` | date_selectorで日付取得できず |  |  |  |
| shimotsuke | 下野新聞 SOON |  | 200/258 | `time, .date` | date_selectorで日付取得できず |  |  | トップ |
| jomo | 上毛新聞 |  | 200/27 | `time, .date` | date_selectorで日付取得できず |  |  | トップ |
| chibanippo | 千葉日報 |  | 200/370 | `time, .date` | date_selectorで日付取得できず |  |  | 新聞購読 |
| kanaloco | カナロコ 神奈川新聞 |  | 200/228 | `time, .date` | date_selectorで日付取得できず |  |  | 新規登録 |
| niigata_nippo | 新潟日報デジタルプラス |  | 200/11 | `time, .date` | date_selectorで日付取得できず |  |  | トップ |
| shinmai | 信濃毎日新聞デジタル |  | 404/0 | `time, .date` | 未確認（検索結果カードなし） |  |  |  |
| shizushin | 静岡新聞 |  | 404/31 | `time, .date` | date_selectorで日付取得できず |  |  | ニュース |
| kyoto_np | 京都新聞 |  | 200/337 | `time, .date` | date_selectorで日付取得できず |  |  | ランキング 京都 滋賀 全国 |
| kobe_np | 神戸新聞NEXT |  | 200/144 | `time, .date` | date_selectorで日付取得できず |  |  | 買い物 |
| chugoku_np | 中国新聞デジタル |  | 200/47 | `time, .date` | 掲載日専用の機械可読属性 | 2026-06-18T17:03:01+09:00 |  | トヨタ、社長選任に９７％賛成 2026/6/18 無料 |
| shikoku_np | 四国新聞 |  | 403/0 | `time, .date` | 未確認（検索結果カードなし） |  |  |  |
| nishinippon | 西日本新聞me | Y | 200/237 | `time, .date` | date_selectorで日付取得できず |  |  | トップ |
| kumamoto_nichi | 熊本日日新聞 |  | 200/135 | `time, .date` | date_selectorで日付取得できず |  |  | 熊本 / |
| ryukyu_shimpo | 琉球新報 |  | 200/79 | `time, .date` | date_selectorで日付取得できず |  |  | 新着 |
| okinawa_times | 沖縄タイムス |  | 200/231 | `time, .date` | date_selectorで日付取得できず |  |  | 新着 |
| iwate_np | 岩手日報 |  | 200/218 | `time, .date` | date_selectorで日付取得できず |  |  | トップページ |
| fukui | 福井新聞 |  | 200/154 | `time, .date` | date_selectorで日付取得できず |  |  |  |
| sanyo | 山陽新聞 |  | 200/149 | `time, .date` | date_selectorで日付取得できず |  |  | 申し込み |
| sanin_chuo | 山陰中央新報 |  | 200/39 | `time, .date` | date_selectorで日付取得できず |  |  | イベント情報 |
| topics | 徳島新聞 |  | 200/215 | `time, .date` | date_selectorで日付取得できず |  |  | 徳島ニュース 一覧 事件・事故 社会 政治・行政 選挙 経済 健康・医療 教育 文化・芸能 気象・防災 訃報 号外 |
| kochi | 高知新聞 |  | 200/198 | `time, .date` | date_selectorで日付取得できず |  |  | 高知の天気 |
| ehime_np | 愛媛新聞 | Y | 404/0 | `time, .date` | 未確認（検索結果カードなし） |  |  |  |
| saga_np | 佐賀新聞 |  | 200/36 | `time, .date` | date_selectorで日付取得できず |  |  | 行政・社会 |
| nikkan_kogyo | 日刊工業新聞 |  | 200/20 | `.ttl .date` | 掲載日専用らしき要素 | （2026/6/19 科学技術・大学） |  | 信州大・トヨタなど、ロボで無機材料開発コンソーシアム設立 （2026/6/19 科学技術・大学） 信州大学アクア・リジェネレーション機構は、トヨタ自動車やデンソー、リガク(東京都昭島市)など12社とA |
| kyodo | 共同通信 |  | 200/52 | `time, .date, .posted-on` | date_selectorで日付取得できず |  |  | 経済 / ビジネス |
| nikkei_business | 日経ビジネス |  | 200/192 | `time, .date` | date_selectorで日付取得できず |  |  | 日経BP 日経ビジネス電子版 日経クロステック 日経クロストレンド 日経メディカル 日経ウーマン ナショナル ジオグラフィック 会社情報 |
| nikkei_xtech | 日経クロステック |  | 200/270 | `time, .date` | date_selectorで日付取得できず |  |  | 日経BP 日経ビジネス電子版 日経クロステック 日経クロストレンド 日経メディカル 日経ウーマン ナショナル ジオグラフィック 会社情報 |
| sbbit | ビジネス+IT |  | 200/30 | `.crd_ttl-pubdate` | date_selectorで日付取得できず |  |  | イベント・セミナー 東京都 2026/08/26 東京都 2026/08/26 自動車業界の需給管理・生販計画の最適化 自動車業界の需給管理・生販計画の最適化 会場受講／ライブ配信／アーカイブ配信（２ |
| nikkan_jidosha | 日刊自動車新聞 電子版 |  | 200/188 | `time, .date` | date_selectorで日付取得できず |  |  | 管理者 |
| denshi_device | 電波新聞デジタル |  | 200/202 | `time, .date, .posted-on` | date_selectorで日付取得できず |  |  | 国際 米州 EMEA 中国 韓国 台湾 ASEAN その他 海外グローバル |
| itmedia | ITmedia | Y | 200/1 | `None` | 検索結果に専用日付selectorなし |  |  |  |
| toyokeizai | 東洋経済オンライン |  | 200/144 | `time, .date` | date_selectorで日付取得できず |  |  | ビジネス |
| diamond | ダイヤモンド・オンライン |  | 200/1 | `time, .date` | date_selectorで日付取得できず |  |  | 記事検索 探したいキーワードや名称、人名などを入れて、虫眼鏡アイコンの検索ボタンをクリックしてください。複数のキーワードをスペースで区切って入力する「AND検索」 になります。 あなたにおすすめ |
| president | PRESIDENT Online |  | 200/30 | `time, .date` | date_selectorで日付取得できず |  |  | NEW ｢安全性の通信簿｣1位の理由 トヨタでも､ホンダでも､日産でもない…米誌が｢世界一安全｣と絶賛した"日本の自動車メーカー"の名前 青葉 やまと 2時間前 |
| ryutsuu_biz | 流通ニュース |  | 200/199 | `time, .date, .posted-on` | date_selectorで日付取得できず |  |  | 流通ニュースについて 各種お問合せ メルマガ登録変更 |
| logistics_today | LOGISTICS TODAY |  | 200/168 | `.list-heading small` | 掲載日専用らしき要素 | 26/06/12 |  | 認証・表彰 岡崎通運、調達物流改善でトヨタから表彰 26/06/12 |
| kentsu | 建通新聞 |  | 200/26 | `time, .date` | date_selectorで日付取得できず |  |  | 速報 |
| shokuhin_sangyo | 食品産業新聞社ニュースWEB |  | 200/83 | `time, .date, .posted-on` | date_selectorで日付取得できず |  |  | 新着記事 全てのニュース 飲料 酒類 乳製品 調味料 菓子 畜産 米・麦 麺 大豆・油 冷食 外食 給食 流通 PR その他 |
| chemical_daily | 化学工業日報 |  | 200/32 | `time, .date, .posted-on` | date_selectorで日付取得できず |  |  | TOP |
| denki_shimbun | 電気新聞ウェブサイト |  | 200/59 | `time, .date, .posted-on` | date_selectorで日付取得できず |  |  | 総合・原子力 |
