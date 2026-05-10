"""Magic values, gh-command tuples, and template-key bindings for doc-gist."""

from __future__ import annotations


TEMP_FILE_PREFIX = "doc-gist-"
TEMP_FILE_SUFFIX = ".html"
WIN_PLATFORM_PREFIX = "win"
DEFAULT_EYEBROW = "doc"

GH_EXECUTABLE = "gh"
GIST_DESCRIPTION_FALLBACK = "Document"
GIST_HOSTNAME_PREFIX = "https://gist.github.com/"
GIST_RAW_HOSTNAME_PREFIX = "https://gist.githubusercontent.com/"
HTMLPREVIEW_URL_PREFIX = "https://htmlpreview.github.io/?"
GH_GIST_DESC_FLAG = "--desc"

ALL_GH_GIST_CREATE_ARGS = ("gist", "create")

FRONTMATTER_DELIMITER = "---"
FRONTMATTER_KEY_TITLE = "title"
FRONTMATTER_KEY_EYEBROW = "eyebrow"
FRONTMATTER_KEY_SUMMARY = "summary"
FRONTMATTER_KEY_DESCRIPTION = "description"

ALL_MARKDOWN_EXTENSIONS = (".md", ".markdown", ".mkd")
ALL_HTML_EXTENSIONS = (".html", ".htm")

CODE_FENCE_MARKER = "```"
HEADING_MARKER = "#"
HORIZONTAL_RULE_MARKER = "---"
BLOCKQUOTE_MARKER = "> "
ALL_UNORDERED_LIST_BULLETS = ("- ", "* ", "+ ")

PLACEHOLDER_BYTE = "\x00"

DOC_DATE_FORMAT = "%Y-%m-%d"
HEADING_LEVEL_H2 = 2
HEADING_LEVEL_H3 = 3
MAXIMUM_HEADING_LEVEL = 4


def make_gist_description(title: str) -> str:
    """Compose the description string passed to `gh gist create --desc`.

    Args:
        title: Document title; falls back to "Document" when empty.

    Returns:
        Human-readable gist description.
    """
    cleaned = title.strip() or GIST_DESCRIPTION_FALLBACK
    return cleaned


def gist_preview_url(gist_user: str, gist_id: str, filename: str) -> str:
    """Build the htmlpreview.github.io URL that renders a gist HTML file.

    Args:
        gist_user: GitHub username that owns the gist.
        gist_id: Hex identifier of the gist.
        filename: Filename inside the gist as preserved by `gh gist create`.

    Returns:
        URL that renders the gist's HTML file when opened in a browser.
    """
    raw_url = f"{GIST_RAW_HOSTNAME_PREFIX}{gist_user}/{gist_id}/raw/{filename}"
    return f"{HTMLPREVIEW_URL_PREFIX}{raw_url}"


def make_template_replacements(
    page_title: str,
    eyebrow: str,
    heading: str,
    meta: str,
    tldr_block: str,
    body: str,
    toc_items: str,
) -> dict[str, str]:
    """Bind rendered fragments to the marker keys consumed by the template filler.

    Args:
        page_title: HTML for the document <title>.
        eyebrow: Eyebrow line above the H1.
        heading: H1 text.
        meta: Header meta strip HTML.
        tldr_block: TL;DR box HTML, or empty string when no summary supplied.
        body: Rendered article body HTML.
        toc_items: TOC nav anchors HTML, or empty string when fewer than two headings.

    Returns:
        Dict mapping each template marker key to its HTML replacement value.
    """
    return {
        "PAGE_TITLE": page_title,
        "EYEBROW": eyebrow,
        "HEADING": heading,
        "META": meta,
        "TLDR_BLOCK": tldr_block,
        "BODY": body,
        "TOC": toc_items,
    }
