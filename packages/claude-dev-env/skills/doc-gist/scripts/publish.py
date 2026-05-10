"""Render Claude-authored markdown into a styled HTML page, upload as a private gist.

Reads markdown (or HTML) from a file or stdin, parses optional YAML-like
front-matter for title/eyebrow/summary, converts the body to HTML with the
Anthropic-inspired template, uploads the result as a private (secret) GitHub
gist via `gh gist create`, and returns an htmlpreview.github.io URL.

Usage:
    python publish.py --input file.md
    python publish.py --input - --title "Plan: X"
"""

from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys
import tempfile
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_skill_root_path = str(Path(__file__).resolve().parent.parent)
if _skill_root_path not in sys.path:
    sys.path.insert(0, _skill_root_path)

from config import constants as doc_gist_constants
from config import rebase_constants as doc_gist_rebase_constants
from scripts import rebase_logic


def _read_input_text(input_argument: str) -> str:
    if input_argument == "-":
        return sys.stdin.read()
    text_path = Path(input_argument).expanduser().resolve()
    if not text_path.exists():
        raise SystemExit(f"Input does not exist: {text_path}")
    return text_path.read_text(encoding="utf-8")


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    delimiter = doc_gist_constants.FRONTMATTER_DELIMITER + "\n"
    if not text.startswith(delimiter):
        return {}, text
    closing = "\n" + doc_gist_constants.FRONTMATTER_DELIMITER + "\n"
    end_position = text.find(closing, len(delimiter))
    if end_position == -1:
        return {}, text
    front_text = text[len(delimiter) : end_position]
    body_text = text[end_position + len(closing) :]
    metadata: dict[str, str] = {}
    for each_line in front_text.splitlines():
        if ":" not in each_line:
            continue
        front_key, _, front_value = each_line.partition(":")
        metadata[front_key.strip()] = front_value.strip().strip('"').strip("'")
    return metadata, body_text


def _safe_html(text: str) -> str:
    return html.escape(text, quote=True)


def _slugify(text: str) -> str:
    cleaned = text.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    return cleaned.strip("-") or "section"


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _render_inline_markdown(text: str) -> str:
    placeholders: list[str] = []

    def _stash(html_fragment: str) -> str:
        marker_text = (
            f"{doc_gist_constants.PLACEHOLDER_BYTE}MD"
            f"{len(placeholders)}{doc_gist_constants.PLACEHOLDER_BYTE}"
        )
        placeholders.append(html_fragment)
        return marker_text

    def replace_inline_code(match: re.Match[str]) -> str:
        return _stash(f"<code>{_safe_html(match.group('code'))}</code>")

    def replace_link(match: re.Match[str]) -> str:
        link_text = _safe_html(match.group("text"))
        href = _safe_html(match.group("href"))
        return _stash(f'<a href="{href}">{link_text}</a>')

    def replace_bold(match: re.Match[str]) -> str:
        return _stash(f"<strong>{_safe_html(match.group('inner'))}</strong>")

    def replace_italic(match: re.Match[str]) -> str:
        return _stash(f"<em>{_safe_html(match.group('inner'))}</em>")

    text = re.sub(r"`(?P<code>[^`]+)`", replace_inline_code, text)
    text = re.sub(r"\[(?P<text>[^\]]+)\]\((?P<href>[^)]+)\)", replace_link, text)
    text = re.sub(r"\*\*(?P<inner>.+?)\*\*", replace_bold, text)
    text = re.sub(r"(?<!\*)\*(?P<inner>[^*\n]+)\*(?!\*)", replace_italic, text)

    text = _safe_html(text)

    for each_index, each_fragment in enumerate(placeholders):
        marker_text = (
            f"{doc_gist_constants.PLACEHOLDER_BYTE}MD"
            f"{each_index}{doc_gist_constants.PLACEHOLDER_BYTE}"
        )
        text = text.replace(marker_text, each_fragment)
    return text


def _md_to_html_and_toc(md_text: str) -> tuple[str, list[tuple[int, str, str]]]:
    lines = md_text.split("\n")
    rendered_lines: list[str] = []
    toc_entries: list[tuple[int, str, str]] = []

    is_inside_code_block = False
    open_list_kind: Optional[str] = None
    paragraph_buffer: list[str] = []

    def flush_paragraph_buffer() -> None:
        if paragraph_buffer:
            joined_paragraph = " ".join(paragraph_buffer)
            rendered_lines.append(f"<p>{_render_inline_markdown(joined_paragraph)}</p>")
            paragraph_buffer.clear()

    def close_open_list() -> None:
        nonlocal open_list_kind
        if open_list_kind is not None:
            rendered_lines.append(f"</{open_list_kind}>")
            open_list_kind = None

    code_fence = doc_gist_constants.CODE_FENCE_MARKER

    for each_line in lines:
        if is_inside_code_block:
            if each_line.startswith(code_fence):
                rendered_lines.append("</code></pre>")
                is_inside_code_block = False
                continue
            rendered_lines.append(_safe_html(each_line))
            continue

        if each_line.startswith(code_fence):
            flush_paragraph_buffer()
            close_open_list()
            rendered_lines.append("<pre><code>")
            is_inside_code_block = True
            continue

        if not each_line.strip():
            flush_paragraph_buffer()
            close_open_list()
            continue

        heading_match = re.match(r"^(?P<hashes>#{1,4})\s+(?P<title>.+)$", each_line)
        if heading_match:
            flush_paragraph_buffer()
            close_open_list()
            heading_level = len(heading_match.group("hashes"))
            heading_raw = heading_match.group("title").strip()
            rendered_heading = _render_inline_markdown(heading_raw)
            anchor_slug = _slugify(_strip_tags(heading_raw))
            rendered_lines.append(
                f'<h{heading_level} id="{anchor_slug}">{rendered_heading}</h{heading_level}>'
            )
            if heading_level in (
                doc_gist_constants.HEADING_LEVEL_H2,
                doc_gist_constants.HEADING_LEVEL_H3,
            ):
                toc_entries.append(
                    (heading_level, anchor_slug, _strip_tags(rendered_heading))
                )
            continue

        if not paragraph_buffer and re.match(r"^-{3,}\s*$", each_line):
            close_open_list()
            rendered_lines.append("<hr>")
            continue

        has_matched_bullet = False
        for each_bullet in doc_gist_constants.ALL_UNORDERED_LIST_BULLETS:
            if each_line.startswith(each_bullet):
                flush_paragraph_buffer()
                if open_list_kind != "ul":
                    close_open_list()
                    rendered_lines.append("<ul>")
                    open_list_kind = "ul"
                bullet_text = each_line.removeprefix(each_bullet)
                rendered_lines.append(
                    f"<li>{_render_inline_markdown(bullet_text)}</li>"
                )
                has_matched_bullet = True
                break
        if has_matched_bullet:
            continue

        ordered_match = re.match(r"^\d+\.\s+(?P<itemtext>.+)$", each_line)
        if ordered_match:
            flush_paragraph_buffer()
            if open_list_kind != "ol":
                close_open_list()
                rendered_lines.append("<ol>")
                open_list_kind = "ol"
            rendered_lines.append(
                f"<li>{_render_inline_markdown(ordered_match.group('itemtext'))}</li>"
            )
            continue

        if each_line.startswith(doc_gist_constants.BLOCKQUOTE_MARKER):
            flush_paragraph_buffer()
            close_open_list()
            quoted = each_line.removeprefix(doc_gist_constants.BLOCKQUOTE_MARKER)
            rendered_lines.append(
                f"<blockquote>{_render_inline_markdown(quoted)}</blockquote>"
            )
            continue

        close_open_list()
        paragraph_buffer.append(each_line.strip())

    flush_paragraph_buffer()
    close_open_list()
    if is_inside_code_block:
        rendered_lines.append("</code></pre>")

    return "\n".join(rendered_lines), toc_entries


def _render_toc(all_toc_entries: list[tuple[int, str, str]]) -> str:
    if len(all_toc_entries) <= 1:
        return ""
    items_html = []
    for each_level, each_anchor, each_text in all_toc_entries:
        is_subheading = each_level != doc_gist_constants.HEADING_LEVEL_H2
        css_class = "sub" if is_subheading else ""
        items_html.append(
            f'<a href="#{_safe_html(each_anchor)}" class="{css_class}">'
            f"{_safe_html(each_text)}</a>"
        )
    return "\n".join(items_html)


def _render_tldr_block(summary: str) -> str:
    if not summary:
        return ""
    rendered_summary = _render_inline_markdown(summary)
    return (
        f'<div class="tldr"><div class="k">TL;DR</div><p>{rendered_summary}</p></div>'
    )


def _render_meta_strip(body_html: str) -> str:
    text_only = _strip_tags(body_html)
    word_count = len(text_only.split())
    today_label = datetime.now(timezone.utc).strftime(
        doc_gist_constants.DOC_DATE_FORMAT
    )
    return f"<span>{_safe_html(today_label)}</span> · <span>{word_count} words</span>"


def _fill_template(template_text: str, all_replacements: dict[str, str]) -> str:
    rendered = template_text
    for each_key, each_value in all_replacements.items():
        marker = f"<!-- TPL:{each_key} -->"
        rendered = rendered.replace(marker, each_value)
    return rendered


def _open_in_browser(target_path: Path) -> None:
    if sys.platform.startswith(doc_gist_constants.WIN_PLATFORM_PREFIX):
        os.startfile(str(target_path))
        return
    webbrowser.open(target_path.resolve().as_uri())


def _open_url_in_browser(target_url: str) -> None:
    webbrowser.open(target_url)


def _create_secret_gist_and_preview_url(
    html_path: Path, title: str, working_dir: Path
) -> tuple[str, str]:
    full_command = [
        doc_gist_constants.GH_EXECUTABLE,
        *doc_gist_constants.ALL_GH_GIST_CREATE_ARGS,
        str(html_path),
        doc_gist_constants.GH_GIST_DESC_FLAG,
        doc_gist_constants.make_gist_description(title),
    ]
    completed = subprocess.run(
        full_command,
        cwd=str(working_dir),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        message_text = completed.stderr.strip() or completed.stdout.strip()
        raise SystemExit(
            f"gh gist create failed:\n{message_text}\n"
            f"Install/authenticate gh, or pass --no-gist."
        )
    last_line = completed.stdout.strip().splitlines()[-1].strip()
    if not last_line.startswith(doc_gist_constants.GIST_HOSTNAME_PREFIX):
        raise SystemExit(f"Unexpected output from gh gist create: {last_line!r}")
    path_after_host = last_line[len(doc_gist_constants.GIST_HOSTNAME_PREFIX) :]
    parts = path_after_host.split("/")
    gist_user = parts[0] if parts else ""
    gist_id = parts[1] if len(parts) > 1 else ""
    if not gist_user or not gist_id:
        raise SystemExit(f"Cannot parse gist URL: {last_line!r}")
    preview = doc_gist_constants.gist_preview_url(gist_user, gist_id, html_path.name)
    return last_line, preview


def _write_html_to_disk(rendered_html: str, requested_path: Optional[str]) -> Path:
    if requested_path is None:
        handle = tempfile.NamedTemporaryFile(
            prefix=doc_gist_constants.TEMP_FILE_PREFIX,
            suffix=doc_gist_constants.TEMP_FILE_SUFFIX,
            delete=False,
            mode="w",
            encoding="utf-8",
        )
        handle.write(rendered_html)
        handle.close()
        return Path(handle.name)
    target_path = Path(requested_path).expanduser().resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(rendered_html, encoding="utf-8")
    return target_path


def _is_html_input(input_argument: str) -> bool:
    lowered = input_argument.lower()
    for each_extension in doc_gist_constants.ALL_HTML_EXTENSIONS:
        if lowered.endswith(each_extension):
            return True
    return False


def _parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render markdown/HTML or a rebase report into a styled doc and upload as a private gist."
    )
    parser.add_argument(
        "--rebase",
        action="store_true",
        help="Switch to rebase-report mode (collects ORIG_HEAD vs HEAD git data; ignores --input).",
    )
    parser.add_argument(
        "--pre",
        default=doc_gist_rebase_constants.DEFAULT_PRE_REF,
        help="Rebase mode: pre-rebase ref (default: ORIG_HEAD).",
    )
    parser.add_argument(
        "--post",
        default=doc_gist_rebase_constants.DEFAULT_POST_REF,
        help="Rebase mode: post-rebase ref (default: HEAD).",
    )
    parser.add_argument(
        "--base",
        default=None,
        help="Rebase mode: base ref. Auto-detected when omitted.",
    )
    parser.add_argument(
        "--whats-new",
        default=None,
        help="Rebase mode: Claude-supplied prose for the 'What's new' bucket at the top of the report.",
    )
    parser.add_argument(
        "--whats-gone",
        default=None,
        help="Rebase mode: Claude-supplied prose for the 'What's gone' bucket at the top of the report.",
    )
    parser.add_argument(
        "--whats-kept",
        default=None,
        help="Rebase mode: Claude-supplied prose for the 'What's kept' bucket at the top of the report.",
    )
    parser.add_argument(
        "--why-summary",
        default=None,
        help="Rebase mode: Claude-supplied prose explaining the pre-vs-post stats for THIS rebase.",
    )
    parser.add_argument(
        "--why-gained-lost",
        default=None,
        help="Rebase mode: Claude-supplied prose explaining why files were gained or lost in THIS rebase.",
    )
    parser.add_argument(
        "--why-files",
        default=None,
        help="Rebase mode: Claude-supplied prose framing the file-by-file section for THIS rebase.",
    )
    parser.add_argument(
        "--why-commits",
        default=None,
        help="Rebase mode: Claude-supplied prose interpreting the commit walk for THIS rebase.",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Doc mode: path to a markdown or HTML file, or '-' for stdin. Required unless --rebase.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Document H1. Overrides front-matter; required when no front-matter title.",
    )
    parser.add_argument(
        "--eyebrow",
        default=None,
        help="Small uppercase text above the H1. Overrides front-matter.",
    )
    parser.add_argument(
        "--summary",
        default=None,
        help="Optional TL;DR paragraph. Overrides front-matter.",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Working directory for gh invocations (default: cwd).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the HTML doc. Defaults to a temp file.",
    )
    parser.add_argument(
        "--no-gist",
        action="store_true",
        help="Skip uploading to a private gist.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Skip opening the report in the default browser.",
    )
    return parser.parse_args(all_argv)


def _run_rebase_mode(
    parsed_arguments: argparse.Namespace,
) -> tuple[str, str, dict[str, int]]:
    return rebase_logic.render_rebase_html(
        repo_argument=parsed_arguments.repo,
        pre_argument=parsed_arguments.pre,
        post_argument=parsed_arguments.post,
        base_argument=parsed_arguments.base,
        whats_new=parsed_arguments.whats_new,
        whats_gone=parsed_arguments.whats_gone,
        whats_kept=parsed_arguments.whats_kept,
        why_summary=parsed_arguments.why_summary,
        why_gained_lost=parsed_arguments.why_gained_lost,
        why_files=parsed_arguments.why_files,
        why_commits=parsed_arguments.why_commits,
    )


def main() -> int:
    """Entry point — read input, render, write, upload as private gist, open in browser.

    Returns:
        Process exit code (0 on success).

    Raises:
        SystemExit: When the input is missing, no title is supplied, or gh upload fails.
    """
    parsed_arguments = _parse_arguments(sys.argv[1:])

    if parsed_arguments.rebase:
        rendered_html, rebase_title, summary_counts = _run_rebase_mode(parsed_arguments)
        target_path = _write_html_to_disk(rendered_html, parsed_arguments.output)
        repo_root = Path(parsed_arguments.repo).expanduser().resolve()
        if not repo_root.exists():
            repo_root = Path.cwd()
        print(f"Wrote {target_path}", file=sys.stderr)
        print(
            f"Commits: {summary_counts['kept']} kept · {summary_counts['changed']} changed · "
            f"{summary_counts['lost']} dropped · {summary_counts['gained']} introduced",
            file=sys.stderr,
        )
        print(
            f"Files: {summary_counts['files_lost']} lost · "
            f"{summary_counts['files_gained']} gained · "
            f"{summary_counts['files_other']} kept-or-shifted",
            file=sys.stderr,
        )
        gist_url = None
        preview_url = None
        if not parsed_arguments.no_gist:
            gist_url, preview_url = _create_secret_gist_and_preview_url(
                target_path, rebase_title, repo_root
            )
            print(f"Gist: {gist_url}", file=sys.stderr)
            print(f"Preview: {preview_url}", file=sys.stderr)
        if not parsed_arguments.no_open:
            if preview_url is not None:
                _open_url_in_browser(preview_url)
                print("Opened gist preview in default browser.", file=sys.stderr)
            else:
                _open_in_browser(target_path)
                print("Opened local file in default browser.", file=sys.stderr)
        if preview_url is not None:
            print(preview_url)
        else:
            print(str(target_path))
        return 0

    if parsed_arguments.input is None:
        raise SystemExit(
            "Doc mode requires --input <path-or-->. Use --rebase for rebase reports."
        )
    raw_text = _read_input_text(parsed_arguments.input)
    treat_as_html = _is_html_input(parsed_arguments.input)

    metadata, body_text = (
        ({}, raw_text) if treat_as_html else _parse_frontmatter(raw_text)
    )

    title = (
        parsed_arguments.title
        or metadata.get(doc_gist_constants.FRONTMATTER_KEY_TITLE, "")
    ).strip()
    if not title:
        raise SystemExit(
            "No title supplied. Pass --title, or include `title:` in the front-matter."
        )
    eyebrow = (
        parsed_arguments.eyebrow
        or metadata.get(
            doc_gist_constants.FRONTMATTER_KEY_EYEBROW,
            doc_gist_constants.DEFAULT_EYEBROW,
        )
    ).strip()
    summary = (
        parsed_arguments.summary
        or metadata.get(doc_gist_constants.FRONTMATTER_KEY_SUMMARY, "")
    ).strip()

    if treat_as_html:
        body_html = body_text
        toc_entries: list[tuple[int, str, str]] = []
    else:
        body_html, toc_entries = _md_to_html_and_toc(body_text)

    tldr_block_html = _render_tldr_block(summary)
    toc_html = _render_toc(toc_entries)
    meta_html = _render_meta_strip(body_html)

    template_path = (
        Path(__file__).parent.parent / "templates" / "document.html.tmpl"
    ).resolve()
    template_text = template_path.read_text(encoding="utf-8")
    replacements = doc_gist_constants.make_template_replacements(
        page_title=_safe_html(title),
        eyebrow=_safe_html(eyebrow),
        heading=_safe_html(title),
        meta=meta_html,
        tldr_block=tldr_block_html,
        body=body_html,
        toc_items=toc_html,
    )
    rendered_html = _fill_template(template_text, replacements)
    target_path = _write_html_to_disk(rendered_html, parsed_arguments.output)

    repo_root = Path(parsed_arguments.repo).expanduser().resolve()
    if not repo_root.exists():
        repo_root = Path.cwd()

    print(f"Wrote {target_path}", file=sys.stderr)

    gist_url = None
    preview_url = None
    if not parsed_arguments.no_gist:
        gist_url, preview_url = _create_secret_gist_and_preview_url(
            target_path, title, repo_root
        )
        print(f"Gist: {gist_url}", file=sys.stderr)
        print(f"Preview: {preview_url}", file=sys.stderr)

    if not parsed_arguments.no_open:
        if preview_url is not None:
            _open_url_in_browser(preview_url)
            print("Opened gist preview in default browser.", file=sys.stderr)
        else:
            _open_in_browser(target_path)
            print("Opened local file in default browser.", file=sys.stderr)

    if preview_url is not None:
        print(preview_url)
    else:
        print(str(target_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
