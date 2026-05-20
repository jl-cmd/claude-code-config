#!/usr/bin/env python3
"""PreToolUse hook: blocks Write/Edit targeting .md files, redirecting to .html.

HTML preserves spatial structure (diffs, timelines, comparisons, diagrams)
that markdown flattens. See https://thariqs.github.io/html-effectiveness/
"""

import json
import os
import sys
import tempfile
from typing import TextIO

from config.md_blocker_constants import (
    EXEMPT_ANYWHERE_FILENAMES,
    EXEMPT_HOME_RELATIVE_DIRECTORIES,
    EXEMPT_PLUGIN_DIRECTORY_SEGMENTS,
    PLUGIN_ROOT_MARKER_DIRECTORY_NAME,
    REPO_ROOT_MARKER_NAME,
)


_markdown_extension = ".md"
_html_effectiveness_url = "https://thariqs.github.io/html-effectiveness/"
_exempt_root_filenames = ("readme.md", "changelog.md")


def _is_exempt_path(file_path: str) -> bool:
    expanded_path = os.path.expanduser(file_path)
    normalized = os.path.normpath(expanded_path).replace("\\", "/")
    lower_normalized = normalized.lower()
    if "/.claude/" in lower_normalized or lower_normalized.startswith(".claude/"):
        return True
    if (
        "/.claude-plugin/" in lower_normalized
        or lower_normalized.startswith(".claude-plugin/")
    ):
        return True
    basename = os.path.basename(normalized)
    exempt_anywhere_filenames = EXEMPT_ANYWHERE_FILENAMES
    if basename.lower() in exempt_anywhere_filenames:
        return True
    if _has_plugin_directory_segment(lower_normalized):
        return True
    canonical_lower_path = (
        os.path.realpath(expanded_path).replace("\\", "/").lower()
    )
    if _is_under_exempt_home_directory(canonical_lower_path):
        return True
    if _is_under_system_temp_directory(canonical_lower_path):
        return True
    if _is_under_plugin_root_marker(normalized):
        return True
    if basename.lower() in _exempt_root_filenames:
        directory = os.path.dirname(normalized)
        if directory in ("", "."):
            return True
        if _is_repo_root_directory(directory):
            return True
    return False


def _has_plugin_directory_segment(lower_normalized_path: str) -> bool:
    exempt_plugin_directory_segments = EXEMPT_PLUGIN_DIRECTORY_SEGMENTS
    for each_directory_segment in exempt_plugin_directory_segments:
        segment_marker = f"/{each_directory_segment}/"
        if segment_marker in lower_normalized_path:
            return True
        if lower_normalized_path.startswith(f"{each_directory_segment}/"):
            return True
    return False


def _is_under_plugin_root_marker(normalized_path: str) -> bool:
    plugin_root_marker_directory_name = PLUGIN_ROOT_MARKER_DIRECTORY_NAME
    directory = os.path.dirname(normalized_path)
    visited_directories: set[str] = set()
    while directory and directory not in visited_directories:
        visited_directories.add(directory)
        marker_path = os.path.join(directory, plugin_root_marker_directory_name)
        if os.path.isdir(marker_path):
            return True
        parent_directory = os.path.dirname(directory)
        if parent_directory == directory:
            break
        directory = parent_directory
    return False


def _is_under_exempt_home_directory(lower_normalized_path: str) -> bool:
    exempt_home_relative_directories = EXEMPT_HOME_RELATIVE_DIRECTORIES
    home_directory = (
        os.path.realpath(os.path.expanduser("~"))
        .replace("\\", "/")
        .rstrip("/")
        .lower()
    )
    if not home_directory:
        return False
    for each_relative_directory in exempt_home_relative_directories:
        exempt_directory = f"{home_directory}/{each_relative_directory.lower()}"
        if lower_normalized_path.startswith(f"{exempt_directory}/"):
            return True
    return False


def _is_under_system_temp_directory(lower_normalized_path: str) -> bool:
    temp_directory = (
        os.path.realpath(tempfile.gettempdir())
        .replace("\\", "/")
        .rstrip("/")
        .lower()
    )
    if not temp_directory:
        return False
    return lower_normalized_path.startswith(f"{temp_directory}/")


def _is_repo_root_directory(directory_path: str) -> bool:
    repo_root_marker_name = REPO_ROOT_MARKER_NAME
    git_marker_path = os.path.join(directory_path, repo_root_marker_name)
    return os.path.exists(git_marker_path)


def _block_reason(file_path: str) -> str:
    return (
        f"BLOCKED: Write/Edit to .md file '{file_path}' is not permitted. "
        "Use .html files instead for documentation. "
        f"See {_html_effectiveness_url} for why HTML "
        "is more effective than Markdown for structured information."
    )


def _block_context() -> str:
    return (
        "Generate a self-contained .html file instead of .md. "
        "Design freely — HTML can express spatial structure, interactivity, "
        "and visual hierarchy that markdown cannot.\n\n"
        "Reference for HTML effectiveness patterns:\n"
        f"{_html_effectiveness_url}\n"
        "Exceptions (.md still allowed):\n"
        "- Files inside .claude/ or .claude-plugin/ directories\n"
        "- SKILL.md anywhere\n"
        "- Files under agents/, skills/, or commands/ directories\n"
        "- Files under any directory whose ancestor contains .claude-plugin/\n"
        "- README.md and CHANGELOG.md at any repo root\n"
        "- Files under ~/.claude/plans/ and ~/SessionLog/\n"
        "- Files under the OS temp directory"
    )


def _block_system_message() -> str:
    return (
        ".md files are blocked in this project — generate a self-contained .html "
        f"file instead. See {_html_effectiveness_url} for "
        "design patterns and examples. Exemptions: .claude/ and .claude-plugin/ "
        "infrastructure, SKILL.md anywhere, agents//skills//commands/ trees, "
        "files under a .claude-plugin/ root, README.md/CHANGELOG.md at any "
        "repo root, ~/.claude/plans/, ~/SessionLog/, and the OS temp directory."
    )


def main() -> None:
    """Read hook input JSON from stdin, deny .md writes or pass through silently.

    Returns:
        None (exits process).
    """
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(input_data, dict):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if not isinstance(tool_name, str):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    if not file_path.lower().endswith(_markdown_extension):
        sys.exit(0)

    if _is_exempt_path(file_path):
        sys.exit(0)

    block_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": _block_reason(file_path),
            "additionalContext": _block_context(),
        },
        "systemMessage": _block_system_message(),
        "suppressOutput": True,
    }

    _emit_hook_result(block_payload, sys.stdout)
    sys.exit(0)


def _emit_hook_result(all_hook_data: dict, output_stream: TextIO) -> None:
    output_stream.write(json.dumps(all_hook_data) + "\n")
    output_stream.flush()


if __name__ == "__main__":
    main()
