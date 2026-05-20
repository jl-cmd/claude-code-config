#!/usr/bin/env python3
"""PreToolUse hook: blocks Write/Edit targeting .md files, redirecting to .html.

HTML preserves spatial structure (diffs, timelines, comparisons, diagrams)
that markdown flattens. See https://thariqs.github.io/html-effectiveness/
"""

import json
import sys
from pathlib import Path
from typing import TextIO


for each_cached_module_name in [
    each_module_key
    for each_module_key in list(sys.modules)
    if each_module_key == "config" or each_module_key.startswith("config.")
]:
    sys.modules.pop(each_cached_module_name, None)
_blocking_directory = str(Path(__file__).resolve().parent)
while _blocking_directory in sys.path:
    sys.path.remove(_blocking_directory)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)

from md_path_exemptions import is_exempt_path  # noqa: E402
from md_path_exemptions import _is_repo_root_directory  # noqa: E402,F401
from md_path_exemptions import _is_under_plugin_root_marker  # noqa: E402,F401


_markdown_extension = ".md"
_html_effectiveness_url = "https://thariqs.github.io/html-effectiveness/"


def _is_exempt_path(file_path: str) -> bool:
    return is_exempt_path(file_path)


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
        "infrastructure, SKILL.md anywhere, agents/, skills/, commands/ trees, "
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
