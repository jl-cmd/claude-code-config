#!/usr/bin/env python3
"""Append an entry to implementation-notes.html under one of four sections.

Used by the `implement` skill. Creates the file with all four sections if it
does not exist; otherwise appends a new <li> under the requested section.

Usage:
    python append_note.py --section decisions --about "Where to write the file" --note "Wrote next to spec rather than CWD because spec path was known."
    python append_note.py --section questions --about "Auth model" --note "Spec didn't say whether sessions persist across restarts." --file ./notes.html
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

from config.notes_constants import ALL_SECTIONS_BY_SLUG, DEFAULT_NOTES_FILENAME


def _build_skeleton() -> str:
    section_blocks = "\n".join(
        f'  <section id="{slug}">\n    <h2>{heading}</h2>\n    <ul></ul>\n  </section>'
        for slug, heading in ALL_SECTIONS_BY_SLUG.items()
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        "  <title>Implementation notes</title>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>Implementation notes</h1>\n"
        f"{section_blocks}\n"
        "</body>\n"
        "</html>\n"
    )


def _ensure_file(target: Path) -> str:
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        skeleton = _build_skeleton()
        target.write_text(skeleton, encoding="utf-8")
        return skeleton
    return target.read_text(encoding="utf-8")


def _render_entry(about: str, note: str) -> str:
    return f"      <li><strong>{html.escape(about)}:</strong> {html.escape(note)}</li>"


def _insert_entry(document: str, slug: str, entry: str) -> str:
    open_marker = f'<section id="{slug}">'
    close_marker = "</ul>"
    section_start = document.find(open_marker)
    if section_start == -1:
        raise RuntimeError(
            f"section '{slug}' not found in file — the file may have been "
            f"edited by hand. Restore the four <section id=...> blocks or "
            f"delete the file so it can be regenerated."
        )
    insert_at = document.find(close_marker, section_start)
    if insert_at == -1:
        raise RuntimeError(
            f"section '{slug}' is missing its closing </ul> — the file may "
            f"have been edited by hand."
        )
    return document[:insert_at] + entry + "\n    " + document[insert_at:]


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append an entry to implementation-notes.html.",
    )
    parser.add_argument(
        "--section",
        required=True,
        choices=sorted(ALL_SECTIONS_BY_SLUG.keys()),
        help="Which section to append under.",
    )
    parser.add_argument(
        "--about",
        required=True,
        help="Short label naming the part of the spec this entry relates to.",
    )
    parser.add_argument(
        "--note",
        required=True,
        help="The decision / deviation / tradeoff / question itself.",
    )
    parser.add_argument(
        "--file",
        default=DEFAULT_NOTES_FILENAME,
        help=(
            f"Path to the notes file. Defaults to ./{DEFAULT_NOTES_FILENAME} "
            f"in the current working directory."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Parse CLI arguments and append one entry to the notes file.

    Returns:
        Process exit code (0 on success).
    """
    arguments = _parse_arguments()
    target_path = Path(arguments.file).expanduser().resolve()
    document = _ensure_file(target_path)
    entry = _render_entry(arguments.about, arguments.note)
    updated = _insert_entry(document, arguments.section, entry)
    target_path.write_text(updated, encoding="utf-8")
    print(f"appended to [{arguments.section}] in {target_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
