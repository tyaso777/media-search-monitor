"""Audit sites whose search result title appears to end with a published date."""

from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup, Tag


ROOT = Path(__file__).resolve().parents[1]
QUERY = "トヨタ"
TRAILING_DATE_RE = re.compile(
    r"(?P<date>"
    r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}(?:\s+\d{1,2}:\d{2})?"
    r"|20\d{2}年\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2})?"
    r"|\d{1,2}/\d{1,2}(?:\s+\d{1,2}:\d{2})?"
    r"|\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2})?"
    r")\s*$"
)


def selected_text(block: Tag, selector: str | None) -> str | None:
    if not selector:
        return None
    for found in block.select(selector):
        text = found.get_text(" ", strip=True)
        if text:
            return text
    return None


def selected_link(block: Tag, selector: str | None) -> Tag | None:
    candidates: list[Tag] = []
    if selector:
        for found in block.select(selector):
            if not isinstance(found, Tag):
                continue
            if found.name == "a" and found.get("href"):
                candidates.append(found)
            else:
                candidates.extend(found.select("a[href]"))
    if not candidates:
        candidates = block.select("a[href]")
    return candidates[0] if candidates else None


def title_from_block(block: Tag, site: dict) -> str | None:
    link = selected_link(block, site.get("url_selector"))
    return selected_text(block, site.get("title_selector")) or (
        link.get_text(" ", strip=True) if link else None
    )


def classify(matches: list[dict], sampled: int) -> str:
    if sampled == 0:
        return "未確認"
    if not matches:
        return "該当なし"
    ratio = len(matches) / sampled
    if ratio >= 0.6:
        return "候補：タイトル末尾日付ルールで対応可能"
    return "一部のみ：要サイト別確認"


def audit() -> list[dict]:
    sites = yaml.safe_load((ROOT / "config/sites.yaml").read_text(encoding="utf-8"))["sites"]
    client = httpx.Client(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 news-monitor-audit/0.1"},
    )
    rows: list[dict] = []
    for site in sites:
        if not site.get("enabled"):
            continue
        page_url = site["search_url_template"].replace(
            "{query}", urllib.parse.quote(QUERY, safe="")
        )
        row = {
            "site_id": site["site_id"],
            "site_name": site["site_name"],
            "requires_playwright": site.get("requires_playwright"),
            "status": None,
            "sampled_titles": 0,
            "trailing_date_matches": [],
            "classification": None,
            "error": None,
        }
        try:
            response = client.get(page_url)
            row["status"] = response.status_code
            soup = BeautifulSoup(response.text, "html.parser")
            titles: list[str] = []
            for block in soup.select(site.get("result_item_selector") or ""):
                title = title_from_block(block, site)
                if title:
                    titles.append(" ".join(title.split()))
                if len(titles) >= 12:
                    break
            row["sampled_titles"] = len(titles)
            for title in titles:
                match = TRAILING_DATE_RE.search(title)
                if match:
                    row["trailing_date_matches"].append(
                        {"title": title[:240], "date": match.group("date")}
                    )
            row["classification"] = classify(
                row["trailing_date_matches"], row["sampled_titles"]
            )
        except Exception as exc:  # noqa: BLE001 - audit should continue.
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["classification"] = "取得エラー"
        rows.append(row)
    return rows


def write_outputs(rows: list[dict]) -> None:
    (ROOT / "work/title_trailing_date_audit.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# タイトル末尾日付 監査メモ",
        "",
        f"- 監査クエリ: `{QUERY}`",
        "- 静的HTTP取得ベース。Playwright必須サイトは追加確認が必要。",
        "- この表は「タイトル文字列の末尾に掲載日らしい表記が含まれるか」を見るもの。タイトル本文中の日付は対象外。",
        "",
        "| site_id | サイト | PW | status | sample | match | 判定 | 日付例 | タイトル例 |",
        "|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for row in rows:
        matches = row["trailing_date_matches"]
        first = matches[0] if matches else {}
        title = (first.get("title") or row.get("error") or "").replace("|", "/")[:120]
        lines.append(
            "| {site_id} | {site_name} | {pw} | {status} | {sampled} | {match_count} | "
            "{classification} | {date} | {title} |".format(
                site_id=row["site_id"],
                site_name=row["site_name"],
                pw="Y" if row["requires_playwright"] else "",
                status=row.get("status"),
                sampled=row["sampled_titles"],
                match_count=len(matches),
                classification=row["classification"],
                date=(first.get("date") or "").replace("|", "/"),
                title=title,
            )
        )
    (ROOT / "docs/title_trailing_date_audit.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    rows = audit()
    write_outputs(rows)
    print(f"audited {len(rows)} enabled sites")


if __name__ == "__main__":
    main()
