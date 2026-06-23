"""Render a small Markdown subset to a standalone HTML document.

This intentionally avoids adding a Markdown dependency. It supports the
documentation patterns used in this project: headings, paragraphs, unordered
lists, fenced code, Markdown links, inline code, and pipe tables.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


def main() -> None:
    """Render one Markdown file to HTML."""

    parser = argparse.ArgumentParser(description="Render Markdown to standalone HTML.")
    parser.add_argument("source", type=Path, help="Markdown file to render")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Output HTML path. Defaults to the source path with .html suffix.",
    )
    args = parser.parse_args()

    output = args.output or args.source.with_suffix(".html")
    markdown = args.source.read_text(encoding="utf-8")
    output.write_text(render_document(markdown, args.source.name), encoding="utf-8")
    print(output)


def render_document(markdown: str, title: str) -> str:
    """Render Markdown text as a standalone HTML document."""

    body = render_markdown(markdown)
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #ffffff;
      --text: #1f2328;
      --muted: #57606a;
      --line: #d8dee4;
      --header: #f6f8fa;
      --link: #0969da;
      --code: #f6f8fa;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: none;
      padding: 24px;
    }}
    h1, h2, h3 {{
      line-height: 1.25;
      margin: 24px 0 12px;
    }}
    h1 {{ font-size: 28px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }}
    h2 {{ font-size: 22px; }}
    h3 {{ font-size: 17px; }}
    p {{ margin: 10px 0; }}
    a {{ color: var(--link); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    code {{
      background: var(--code);
      border-radius: 4px;
      padding: 0.15em 0.35em;
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 0.92em;
    }}
    pre {{
      background: var(--code);
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: auto;
      padding: 12px;
    }}
    pre code {{ background: transparent; padding: 0; }}
    ul {{ padding-left: 24px; }}
    .table-wrap {{
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: auto;
      margin: 16px 0 24px;
      max-height: 80vh;
    }}
    table {{
      border-collapse: separate;
      border-spacing: 0;
      min-width: 1600px;
      width: max-content;
    }}
    th, td {{
      border-right: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      max-width: 460px;
      min-width: 100px;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      white-space: normal;
    }}
    th {{
      background: var(--header);
      position: sticky;
      top: 0;
      z-index: 1;
      font-weight: 600;
    }}
    tr:nth-child(even) td {{ background: #fbfbfc; }}
    th:first-child, td:first-child {{
      left: 0;
      position: sticky;
      z-index: 2;
      min-width: 150px;
    }}
    th:nth-child(3), td:nth-child(3) {{
      max-width: 90px;
      min-width: 90px;
      width: 90px;
      word-break: break-word;
    }}
    th:nth-child(4), td:nth-child(4) {{
      max-width: 160px;
      min-width: 140px;
      width: 150px;
      word-break: break-word;
    }}
    th:nth-child(5), td:nth-child(5) {{
      max-width: 230px;
      min-width: 180px;
      width: 210px;
      word-break: break-word;
    }}
    th:nth-child(7), td:nth-child(7) {{
      max-width: 80px;
      min-width: 70px;
      width: 70px;
      word-break: break-word;
    }}
    th:nth-child(8), td:nth-child(8) {{
      max-width: 310px;
      min-width: 240px;
      width: 280px;
      word-break: break-word;
    }}
    th:nth-child(9), td:nth-child(9) {{
      max-width: 90px;
      min-width: 80px;
      width: 85px;
      word-break: break-word;
    }}
    td:first-child {{ background: #fff; font-weight: 600; }}
    tr:nth-child(even) td:first-child {{ background: #fbfbfc; }}
    th:first-child {{ z-index: 3; }}
  </style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def render_markdown(markdown: str) -> str:
    """Render the Markdown subset used by local docs."""

    lines = markdown.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    list_open = False
    code_open = False
    code_lines: list[str] = []
    i = 0

    def flush_paragraph() -> None:
        if paragraph:
            out.append(f"<p>{render_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            out.append("</ul>")
            list_open = False

    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            if code_open:
                out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines.clear()
                code_open = False
            else:
                flush_paragraph()
                close_list()
                code_open = True
            i += 1
            continue
        if code_open:
            code_lines.append(line)
            i += 1
            continue

        if _is_table_start(lines, i):
            flush_paragraph()
            close_list()
            table_lines = [line]
            i += 1
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            out.append(render_table(table_lines))
            continue

        if not line.strip():
            flush_paragraph()
            close_list()
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{render_inline(heading.group(2).strip())}</h{level}>")
            i += 1
            continue

        if line.startswith("- "):
            flush_paragraph()
            if not list_open:
                out.append("<ul>")
                list_open = True
            out.append(f"<li>{render_inline(line[2:].strip())}</li>")
            i += 1
            continue

        paragraph.append(line.strip())
        i += 1

    flush_paragraph()
    close_list()
    if code_open:
        out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    return "\n".join(out)


def render_table(lines: list[str]) -> str:
    """Render a pipe table."""

    header = split_table_row(lines[0])
    body = [split_table_row(line) for line in lines[2:]]
    parts = ["<div class=\"table-wrap\"><table><thead><tr>"]
    parts.extend(f"<th>{render_inline(cell)}</th>" for cell in header)
    parts.append("</tr></thead><tbody>")
    for row in body:
        parts.append("<tr>")
        parts.extend(f"<td>{render_inline(cell)}</td>" for cell in row)
        parts.append("</tr>")
    parts.append("</tbody></table></div>")
    return "".join(parts)


def split_table_row(line: str) -> list[str]:
    """Split one escaped-pipe Markdown table row into cells."""

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    trimmed = line.strip()
    if trimmed.startswith("|"):
        trimmed = trimmed[1:]
    if trimmed.endswith("|"):
        trimmed = trimmed[:-1]
    for char in trimmed:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def render_inline(text: str) -> str:
    """Render inline Markdown constructs."""

    placeholders: list[str] = []

    def stash(value: str) -> str:
        placeholders.append(value)
        return f"\x00{len(placeholders) - 1}\x00"

    def code_repl(match: re.Match[str]) -> str:
        return stash(f"<code>{html.escape(match.group(1))}</code>")

    def link_repl(match: re.Match[str]) -> str:
        label = render_inline(match.group(1))
        url = html.escape(match.group(2), quote=True)
        return stash(f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>')

    text = re.sub(r"`([^`]+)`", code_repl, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, text)
    rendered = html.escape(text)
    for index, value in enumerate(placeholders):
        rendered = rendered.replace(f"\x00{index}\x00", value)
    return rendered


def _is_table_start(lines: list[str], index: int) -> bool:
    """Return true if lines[index] starts a Markdown table."""

    return (
        index + 1 < len(lines)
        and lines[index].startswith("|")
        and lines[index + 1].startswith("|")
        and set(lines[index + 1].replace("|", "").replace(" ", "").strip()) <= {"-", ":"}
    )


if __name__ == "__main__":
    main()
