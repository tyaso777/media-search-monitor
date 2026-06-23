"""Audit where each configured site exposes published dates."""

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
DATE_RE = re.compile(
    r"(20\d{2}[年/.-]\s*\d{1,2}[月/.-]\s*\d{1,2}"
    r"|\d{1,2}/\d{1,2}(?:\s+\d{1,2}:\d{2})?"
    r"|\d{1,2}月\d{1,2}日"
    r"|\d{1,2}:\d{2})"
)


def selected_text(block: Tag, selector: str | None) -> str | None:
    if not selector:
        return None
    for found in block.select(selector):
        text = found.get_text(" ", strip=True)
        if text:
            return text
    return None


def selected_date(block: Tag, selector: str | None) -> tuple[str | None, str | None, str | None]:
    if not selector:
        return None, None, None
    for found in block.select(selector):
        for attr in ("datetime", "content", "data-date", "data-published"):
            value = found.get(attr)
            if value:
                return str(value).strip(), selector, f"{found.name}[{attr}]"
        text = found.get_text(" ", strip=True)
        if text:
            return text, selector, found.name
    return None, selector, None


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


def title_has_date(title: str | None) -> bool:
    return bool(title and DATE_RE.search(title))


def classify(site: dict, first: dict | None) -> str:
    if not first:
        return "未確認（検索結果カードなし）"
    date_text = first.get("date_text")
    date_source = first.get("date_source") or ""
    title = first.get("title") or ""
    if not site.get("date_selector"):
        return "検索結果に専用日付selectorなし"
    if date_text:
        title_match = DATE_RE.search(title)
        if date_text == title or (
            title_match and title_match.group(0) in date_text and len(date_text) > 30
        ):
            return "危険：タイトル/カード本文由来の可能性"
        if "datetime" in date_source or "content" in date_source:
            return "掲載日専用の機械可読属性"
        return "掲載日専用らしき要素"
    return "date_selectorで日付取得できず"


def audit() -> list[dict]:
    sites = yaml.safe_load((ROOT / "config/sites.yaml").read_text(encoding="utf-8"))["sites"]
    rows: list[dict] = []
    client = httpx.Client(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 news-monitor-audit/0.1"},
    )
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
            "search_url": page_url,
            "date_selector": site.get("date_selector"),
            "title_selector": site.get("title_selector"),
            "result_item_selector": site.get("result_item_selector"),
            "status": None,
            "error": None,
            "items": 0,
            "first": None,
            "classification": None,
        }
        try:
            response = client.get(page_url)
            row["status"] = response.status_code
            soup = BeautifulSoup(response.text, "html.parser")
            blocks = soup.select(site["result_item_selector"] or "")
            row["items"] = len(blocks)
            if blocks:
                block = blocks[0]
                link = selected_link(block, site.get("url_selector"))
                title = selected_text(block, site.get("title_selector")) or (
                    link.get_text(" ", strip=True) if link else None
                )
                date_text, date_selector, date_source = selected_date(
                    block, site.get("date_selector")
                )
                card_text = block.get_text(" ", strip=True)
                row["first"] = {
                    "title": title[:200] if title else None,
                    "url": urllib.parse.urljoin(page_url, link.get("href")) if link else None,
                    "date_text": date_text,
                    "date_selector": date_selector,
                    "date_source": date_source,
                    "title_has_date": title_has_date(title),
                    "card_date_candidates": DATE_RE.findall(card_text)[:5],
                    "card_text_head": card_text[:240],
                }
            row["classification"] = classify(site, row["first"])
        except Exception as exc:  # noqa: BLE001 - audit should continue across sites.
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["classification"] = "取得エラー"
        rows.append(row)
    return rows


def write_outputs(rows: list[dict]) -> None:
    work_dir = ROOT / "work"
    work_dir.mkdir(exist_ok=True)
    (work_dir / "date_location_audit.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# 掲載日箇所 監査メモ",
        "",
        f"- 監査クエリ: `{QUERY}`",
        "- 静的HTTP取得ベース。Playwright必須サイトは追加確認が必要。",
        "",
        "| site_id | サイト | PW | status/items | date_selector | 判定 | 取得日付例 | タイトル日付 | メモ |",
        "|---|---|---:|---:|---|---|---|---:|---|",
    ]
    for row in rows:
        first = row.get("first") or {}
        note = row.get("error") or first.get("card_text_head") or ""
        note = note.replace("|", "/").replace("\n", " ")[:100]
        lines.append(
            "| {site_id} | {site_name} | {pw} | {status}/{items} | `{date_selector}` | "
            "{classification} | {date} | {title_date} | {note} |".format(
                site_id=row["site_id"],
                site_name=row["site_name"],
                pw="Y" if row["requires_playwright"] else "",
                status=row.get("status"),
                items=row.get("items"),
                date_selector=row.get("date_selector"),
                classification=row.get("classification"),
                date=(first.get("date_text") or "").replace("|", "/"),
                title_date="Y" if first.get("title_has_date") else "",
                note=note,
            )
        )
    (ROOT / "docs/site_date_location_audit.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    rows = audit()
    write_outputs(rows)
    print(f"audited {len(rows)} enabled sites")


if __name__ == "__main__":
    main()
