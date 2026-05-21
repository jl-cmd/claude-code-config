#!/usr/bin/env python3
"""PreToolUse hook: blocks Write/Edit targeting .md files, redirecting to .html.

HTML preserves spatial structure (diffs, timelines, comparisons, diagrams)
that markdown flattens. See https://thariqs.github.io/html-effectiveness/
"""

import json
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

_blocking_directory = str(Path(__file__).resolve().parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)

from hooks_constants.md_to_html_blocker_constants import (  # noqa: E402
    ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES,
    ALL_EXEMPT_ANYWHERE_FILENAMES,
    ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES,
    ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS,
    CLAUDE_DEV_ENV_REPO_NAME_SEGMENT,
    CLAUDE_DIRECTORY_NAME,
    PACKAGES_TOP_LEVEL_SEGMENT,
    PLUGIN_ROOT_MARKER_DIRECTORY_NAME,
)
from md_path_exemptions import is_exempt_path  # noqa: E402


_markdown_extension = ".md"
_html_effectiveness_url = "https://thariqs.github.io/html-effectiveness/"
_claude_dev_env_source_anchor = (
    f"{PACKAGES_TOP_LEVEL_SEGMENT}/{CLAUDE_DEV_ENV_REPO_NAME_SEGMENT}/"
)


def _format_filename_for_display(filename: str) -> str:
    if filename.lower().endswith(_markdown_extension):
        stem_length = len(filename) - len(_markdown_extension)
        return filename[:stem_length].upper() + _markdown_extension
    return filename


def _exempt_anywhere_filenames_summary() -> str:
    all_display_filenames = [
        _format_filename_for_display(each_filename)
        for each_filename in ALL_EXEMPT_ANYWHERE_FILENAMES
    ]
    return ", ".join(all_display_filenames)


def _exempt_plugin_segments_summary() -> str:
    return ", ".join(f"{each_segment}/" for each_segment in ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS)


def _exempt_home_directories_summary() -> str:
    return ", ".join(f"~/{each_directory}/" for each_directory in ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES)


def _claude_dev_env_source_directories_summary() -> str:
    all_directories_sorted = sorted(ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES)
    formatted_directories = ",".join(all_directories_sorted)
    return f"{_claude_dev_env_source_anchor}{{{formatted_directories}}}/"


def _block_reason(file_path: str) -> str:
    return (
        f"BLOCKED: Write/Edit to .md file '{file_path}' is not permitted. "
        "Use .html files instead for documentation. "
        f"See {_html_effectiveness_url} for why HTML "
        "is more effective than Markdown for structured information."
    )


def _block_context() -> str:
    exempt_filenames_summary = _exempt_anywhere_filenames_summary()
    plugin_segments_summary = _exempt_plugin_segments_summary()
    home_directories_summary = _exempt_home_directories_summary()
    claude_dev_env_source_summary = _claude_dev_env_source_directories_summary()
    return (
        "Generate a self-contained .html file instead of .md. "
        "Design freely — HTML can express spatial structure, interactivity, "
        "and visual hierarchy that markdown cannot.\n\n"
        "Reference for HTML effectiveness patterns:\n"
        f"{_html_effectiveness_url}\n"
        "Exceptions (.md still allowed):\n"
        f"- Files inside {CLAUDE_DIRECTORY_NAME}/ or {PLUGIN_ROOT_MARKER_DIRECTORY_NAME}/ directories\n"
        f"- {exempt_filenames_summary} anywhere\n"
        f"- Files under {plugin_segments_summary} directories\n"
        f"- Files under {claude_dev_env_source_summary} source directories\n"
        f"- Files under any directory whose ancestor contains {PLUGIN_ROOT_MARKER_DIRECTORY_NAME}/\n"
        "- README.md and CHANGELOG.md at any repo root\n"
        f"- Files under {home_directories_summary}\n"
        "- Files under the OS temp directory"
    )


def _block_system_message() -> str:
    exempt_filenames_summary = _exempt_anywhere_filenames_summary()
    plugin_segments_summary = _exempt_plugin_segments_summary()
    home_directories_summary = _exempt_home_directories_summary()
    claude_dev_env_source_summary = _claude_dev_env_source_directories_summary()
    return (
        ".md files are blocked in this project — generate a self-contained .html "
        f"file instead. See {_html_effectiveness_url} for "
        f"design patterns and examples. Exemptions: {CLAUDE_DIRECTORY_NAME}/ and "
        f"{PLUGIN_ROOT_MARKER_DIRECTORY_NAME}/ infrastructure, "
        f"{exempt_filenames_summary} anywhere, {plugin_segments_summary} trees, "
        f"{claude_dev_env_source_summary} source trees, "
        f"files under a {PLUGIN_ROOT_MARKER_DIRECTORY_NAME}/ root, "
        f"README.md/CHANGELOG.md at any repo root, {home_directories_summary}, "
        "and the OS temp directory."
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

    if is_exempt_path(file_path):
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
