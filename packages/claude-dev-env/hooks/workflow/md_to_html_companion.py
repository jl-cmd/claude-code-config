#!/usr/bin/env python3
"""PostToolUse hook: generates a companion .html from a .md file after write.

The .md serves as a first draft; the .html is a 2nd-pass refinement with
dark-mode styling that also validates the .md structure.
See https://thariqs.github.io/html-effectiveness/
"""

import json
import os
import re
import sys


def _is_exempt_path(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    return "/.claude/" in normalized or normalized.startswith(".claude/")


def _md_to_html(markdown_text: str) -> str:
    text = markdown_text.strip()
    if not text:
        return ""

    all_lines = text.split("\n")
    all_output_lines: list[str] = []
    is_in_code_block = False
    paragraph_buffer: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_buffer:
            all_output_lines.append("<p>" + "\n".join(paragraph_buffer) + "</p>")
            paragraph_buffer.clear()

    for each_line in all_lines:
        if each_line.startswith("```"):
            if is_in_code_block:
                all_output_lines.append("</code></pre>")
                is_in_code_block = False
            else:
                flush_paragraph()
                lang = each_line[3:].strip()
                if lang:
                    all_output_lines.append(f'<pre><code class="language-{lang}">')
                else:
                    all_output_lines.append("<pre><code>")
                is_in_code_block = True
            continue

        if is_in_code_block:
            all_output_lines.append(each_line)
            continue

        stripped = each_line.strip()
        if not stripped:
            flush_paragraph()
            continue

        if stripped.startswith("# "):
            flush_paragraph()
            all_output_lines.append(f"<h1>{_inline_format(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            flush_paragraph()
            all_output_lines.append(f"<h2>{_inline_format(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            flush_paragraph()
            all_output_lines.append(f"<h3>{_inline_format(stripped[4:])}</h3>")
        elif stripped.startswith("#### "):
            flush_paragraph()
            all_output_lines.append(f"<h4>{_inline_format(stripped[5:])}</h4>")
        elif stripped.startswith("##### "):
            flush_paragraph()
            all_output_lines.append(f"<h5>{_inline_format(stripped[6:])}</h5>")
        elif stripped.startswith("###### "):
            flush_paragraph()
            all_output_lines.append(f"<h6>{_inline_format(stripped[7:])}</h6>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            all_output_lines.append(f"<li>{_inline_format(stripped[2:])}</li>")
        elif re.match(r"^\d+\.\s", stripped):
            flush_paragraph()
            content = re.sub(r"^\d+\.\s", "", stripped)
            all_output_lines.append(f"<li>{_inline_format(content)}</li>")
        elif stripped == "---":
            flush_paragraph()
            all_output_lines.append("<hr>")
        elif stripped.startswith("> "):
            flush_paragraph()
            all_output_lines.append(
                f"<blockquote>{_inline_format(stripped[2:])}</blockquote>"
            )
        else:
            paragraph_buffer.append(_inline_format(stripped))

    if is_in_code_block:
        all_output_lines.append("</code></pre>")
    flush_paragraph()

    return "\n".join(all_output_lines)


def _inline_format(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _extract_title(markdown_text: str) -> str:
    for each_line in markdown_text.strip().split("\n"):
        stripped = each_line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return "Document"


def _html_template(title: str, body: str) -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: system-ui, -apple-system, sans-serif;
    background: rgb({bg}); color: rgb({fg}); line-height: {line_height};
    padding: {body_padding}; max-width: {max_width}; margin: 0 auto;
  }}
  h1 {{ font-size: {h1_size}; border-bottom: 1px solid rgb({border}); padding-bottom: 0.5rem; margin: 1.5rem 0 1rem; }}
  h2 {{ font-size: {h2_size}; margin: 1.25rem 0 0.75rem; color: rgb({accent}); }}
  h3 {{ font-size: {h3_size}; margin: 1rem 0 0.5rem; }}
  p {{ margin: 0.75rem 0; }}
  a {{ color: rgb({accent}); }}
  code {{
    font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: {code_size};
    background: rgb({surface}); padding: 0.15em 0.35em; border-radius: 3px;
  }}
  pre {{
    background: rgb({surface}); border: 1px solid rgb({border});
    border-radius: 6px; padding: 1rem; overflow-x: auto; margin: 0.75rem 0;
  }}
  pre code {{ background: none; padding: 0; }}
  ul, ol {{ padding-left: 1.5rem; margin: 0.5rem 0; }}
  li {{ margin: 0.25rem 0; }}
  strong {{ color: rgb({strong}); }}
  table {{ width: {table_width}; border-collapse: collapse; margin: 0.75rem 0; }}
  th, td {{ padding: 0.5rem 0.75rem; text-align: left; border: 1px solid rgb({border}); }}
  th {{ background: rgb({surface}); font-weight: {th_weight}; }}
  hr {{ border: none; border-top: 1px solid rgb({border}); margin: 1.5rem 0; }}
  blockquote {{
    border-left: 3px solid rgb({accent}); padding-left: 1rem;
    color: rgb({muted}); margin: 0.75rem 0;
  }}
</style>
</head>
<body>
{body}
</body>
</html>""".format(
        title=title,
        body=body,
        bg="13, 17, 23",
        fg="201, 209, 217",
        border="48, 54, 61",
        accent="88, 166, 255",
        muted="139, 148, 158",
        surface="22, 27, 34",
        strong="240, 246, 252",
        line_height="1.6",
        body_padding="2rem",
        max_width="960px",
        h1_size="1.6rem",
        h2_size="1.25rem",
        h3_size="1.1rem",
        code_size="0.85rem",
        table_width="100%",
        th_weight="600",
    )


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(input_data, dict):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path or not file_path.lower().endswith(".md"):
        sys.exit(0)

    if _is_exempt_path(file_path):
        sys.exit(0)

    if not os.path.exists(file_path):
        sys.exit(0)

    try:
        with open(file_path, encoding="utf-8") as f:
            md_content = f.read()
    except OSError:
        sys.exit(0)

    if not md_content.strip():
        sys.exit(0)

    title = _extract_title(md_content)
    html_body = _md_to_html(md_content)
    html_content = _html_template(title=title, body=html_body)

    html_path = os.path.splitext(file_path)[0] + ".html"
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except OSError:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
