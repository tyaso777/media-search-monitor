# Initial Media Targets

This initial target list intentionally includes a broad mix of national newspapers, regional papers, and trade/industry media.

## Scope

- Only public search result pages are configured.
- Article body retrieval is out of scope.
- Login-only pages, paid article bodies, CAPTCHA handling, and access circumvention are out of scope.
- `max_pages` starts at `1` for every real site.

## Selector Status

Most real-site entries use conservative broad selectors such as `article`, `.search-result`, `.article-list li`, and WordPress-style `.post` selectors. These are initial crawl targets, not final site-specific parsers.

Follow-up site research should add one fixture and one parser test per site or site group, then tighten selectors in `config/sites.yaml`.

## Coverage

- National/business newspapers: Asahi, Yomiuri, Mainichi, Sankei, Nikkei, Tokyo, Chunichi, Kyodo, Jiji candidate, Nikkei Business, Nikkei XTech, Business+IT
- Regional newspapers: Hokkaido, Kahoku, Toonippo, Sakigake, Iwate, Yamagata, Fukushima Minyu, Shimotsuke, Jomo, Chiba Nippo, Kanagawa, Niigata, Shinmai, Shizuoka, Fukui, Kyoto, Kobe, Chugoku, Sanyo, Sanin Chuo, Shikoku, Tokushima, Kochi, Ehime, Nishinippon, Saga, Kumamoto, Ryukyu Shimpo, Okinawa Times
- Trade/industry media: Nikkan Kogyo, Nikkan Jidosha, Automotive News Japan, Dempa Digital, ITmedia, Impress Watch, Toyo Keizai, Diamond, President, Ryutsuu News, LOGISTICS TODAY, Kentsu, Shokuhin Sangyo, Chemical Daily, Denki Shimbun
