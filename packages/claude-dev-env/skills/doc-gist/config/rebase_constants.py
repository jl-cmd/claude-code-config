"""Rebase-mode constants for doc-gist — git command tuples, status tables, diff parsing."""

from __future__ import annotations


DEFAULT_PRE_REF = "ORIG_HEAD"
DEFAULT_POST_REF = "HEAD"
DETACHED_HEAD_LABEL = "detached HEAD"
DASH_SHA_PREFIX = "---"
DIFF_LINE_LIMIT_PER_FILE = 400

DIFF_HEADER_DIFF_PREFIX = "diff --git"
DIFF_HEADER_INDEX_PREFIX = "index "
DIFF_HEADER_OLD_FILE_PREFIX = "--- "
DIFF_HEADER_NEW_FILE_PREFIX = "+++ "
DIFF_HUNK_PREFIX = "@@"
DIFF_ADDITION_PREFIX = "+"
DIFF_DELETION_PREFIX = "-"
PATH_SEPARATOR_FOR_DIFF = "--"

ALL_UPSTREAM_FALLBACK_REFS = (
    "@{upstream}",
    "origin/main",
    "origin/master",
    "main",
    "master",
)
ALL_DANGEROUS_REF_CHARACTERS = (" ", ";", "|", "&", "`", "$", "\n", "\r", "<", ">")

ALL_GIT_REV_PARSE_SHORT_ARGS = ("rev-parse", "--short")
ALL_GIT_REV_PARSE_SHOW_TOPLEVEL_ARGS = ("rev-parse", "--show-toplevel")
ALL_GIT_REV_PARSE_ABBREV_REF_HEAD_ARGS = ("rev-parse", "--abbrev-ref", "HEAD")
ALL_GIT_REV_PARSE_VERIFY_QUIET_ARGS = ("rev-parse", "--verify", "--quiet")
ALL_GIT_LOG_ONE_FORMAT_SUBJECT_ARGS = ("log", "-1", "--format=%s")
ALL_GIT_MERGE_BASE_ARGS = ("merge-base",)
ALL_GIT_RANGE_DIFF_NO_COLOR_ARGS = ("range-diff", "--no-color")
ALL_GIT_DIFF_NUMSTAT_ARGS = ("diff", "--numstat")
ALL_GIT_DIFF_SHORTSTAT_ARGS = ("diff", "--shortstat")
ALL_GIT_REV_LIST_COUNT_ARGS = ("rev-list", "--count")
ALL_GIT_DIFF_PATCH_ARGS = ("diff", "--no-color")

RANGE_DIFF_LINE_REGEX = (
    r"^\s*(?P<pre_index>\S+):\s+(?P<pre_sha>\S+)\s+(?P<status>[=!<>])\s+"
    r"(?P<post_index>\S+):\s+(?P<post_sha>\S+)\s+(?P<subject>.*?)\s*$"
)

STATUS_KEPT = "="
STATUS_CHANGED = "!"
STATUS_LOST_GLYPH = "<"
STATUS_GAINED_GLYPH = ">"

STATUS_LOST_LABEL = "lost"
STATUS_GAINED_LABEL = "gained"
STATUS_MODIFIED_LABEL = "modified"
FALLBACK_CSS_CLASS = "kept"
FALLBACK_STATUS_DESCRIPTION = "Unknown status"
STATUS_PORTED_LABEL = "ported"

ALL_STATUS_LABEL_BY_GLYPH = {
    STATUS_KEPT: ("kept", "Patch unchanged"),
    STATUS_CHANGED: ("changed", "Patch text changed during rebase"),
    STATUS_LOST_GLYPH: (STATUS_LOST_LABEL, "Commit dropped from the rebased branch"),
    STATUS_GAINED_GLYPH: (STATUS_GAINED_LABEL, "Commit introduced by the rebase"),
}

ALL_DISPLAY_GLYPH_BY_STATUS = {
    STATUS_KEPT: STATUS_KEPT,
    STATUS_CHANGED: STATUS_CHANGED,
    STATUS_LOST_GLYPH: "−",
    STATUS_GAINED_GLYPH: "+",
}


def make_rebase_template_replacements(
    page_title: str,
    eyebrow: str,
    heading: str,
    meta: str,
    context: str,
    whats_new: str,
    whats_gone: str,
    whats_kept: str,
    base_label: str,
    pre_short: str,
    post_short: str,
    pre_summary_list: str,
    post_summary_list: str,
    lost_count: str,
    gained_count: str,
    lost_block: str,
    gained_block: str,
    file_rows: str,
    commit_walk: str,
    why_summary: str,
    why_gained_lost: str,
    why_files: str,
    why_commits: str,
) -> dict[str, str]:
    """Bind rendered HTML fragments to the rebase template's marker keys.

    Args:
        page_title: HTML for the document <title>.
        eyebrow: Eyebrow line above the H1.
        heading: H1 text.
        meta: Header meta strip HTML.
        context: Prompt-box context HTML.
        tldr: TL;DR paragraph HTML.
        base_label: Plain text base ref label.
        pre_short: Short sha of pre-rebase tip.
        post_short: Short sha of post-rebase tip.
        pre_summary_list: Pre-rebase summary panel <li> HTML.
        post_summary_list: Post-rebase summary panel <li> HTML.
        lost_count: String count of lost files.
        gained_count: String count of gained files.
        lost_block: HTML block for the lost-files panel.
        gained_block: HTML block for the gained-files panel.
        file_rows: HTML for every per-file panel.
        commit_walk: HTML for the commit walk section.

    Returns:
        Dict mapping each rebase template marker key to its HTML replacement value.
    """
    return {
        "PAGE_TITLE": page_title,
        "EYEBROW": eyebrow,
        "HEADING": heading,
        "META": meta,
        "CONTEXT": context,
        "WHATS_NEW": whats_new,
        "WHATS_GONE": whats_gone,
        "WHATS_KEPT": whats_kept,
        "BASE_LABEL": base_label,
        "PRE_SHORT": pre_short,
        "POST_SHORT": post_short,
        "PRE_SUMMARY_LIST": pre_summary_list,
        "POST_SUMMARY_LIST": post_summary_list,
        "LOST_COUNT": lost_count,
        "GAINED_COUNT": gained_count,
        "LOST_BLOCK": lost_block,
        "GAINED_BLOCK": gained_block,
        "FILE_ROWS": file_rows,
        "COMMIT_WALK": commit_walk,
        "WHY_SUMMARY": why_summary,
        "WHY_GAINED_LOST": why_gained_lost,
        "WHY_FILES": why_files,
        "WHY_COMMITS": why_commits,
    }
