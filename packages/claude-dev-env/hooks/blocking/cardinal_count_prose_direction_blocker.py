#!/usr/bin/env python3
"""PreToolUse hook: block directional phrasing of the cardinal-count gate condition.

The rule docstring-prose-matches-implementation.md describes the gate
check_docstring_cardinal_count_matches_constant_family, whose binding condition
is symmetric: it fires whenever a docstring's stated cardinal count is not equal
to the size of a referenced constant family, so a count above the family size
and a count below it both trip the gate. When the rule prose describes that
condition with a directional comparator -- 'a count below the family size' or
'references more members ... than the count names' -- and names no symmetry
marker beside it, it narrows the gate to one direction and drifts from what the
detector flags. This hook fires on a Write, Edit, or MultiEdit targeting that
rule file and blocks the write when the cardinal-gate anchor and an unbalanced
directional comparator both appear, so the prose is restated symmetrically in
the same change. A write that describes the condition as 'a count that differs
from the family size' is allowed.
"""

import json
import re
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.cardinal_count_prose_direction_blocker_constants import (  # noqa: E402
    ALL_DIRECTIONAL_PROSE_PATTERNS,
    CARDINAL_GATE_ANCHOR,
    DIRECTION_ADDITIONAL_CONTEXT,
    DIRECTION_MESSAGE_TEMPLATE,
    DIRECTION_SYSTEM_MESSAGE,
    MAX_DIRECTION_ISSUES,
    SYMMETRY_MARKER_PATTERN,
    SYMMETRY_WINDOW_RADIUS,
    TARGET_RULE_BASENAME,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.multi_edit_reconstruction import (  # noqa: E402
    apply_edits,
    edits_for_tool,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def is_target_rule_file(file_path: str) -> bool:
    """Return whether file_path names the docstring-prose rule this hook guards.

    Args:
        file_path: The destination path of the write or edit.

    Returns:
        True when the path basename is the target rule basename.
    """
    return Path(file_path).name == TARGET_RULE_BASENAME


def find_directional_prose_drift(content: str) -> list[str]:
    """Return one issue per directional comparator that narrows the cardinal gate.

    The check binds only when the cardinal-gate anchor token appears in the
    content, proving the prose describes
    check_docstring_cardinal_count_matches_constant_family. Each directional
    comparator that scopes the count-versus-family relationship to one direction
    -- 'below the family size', 'more members ... than the count names' -- is an
    issue, unless a symmetry marker ('differs', 'both', 'either', 'above and
    below') sits beside it, since the gate fires on any mismatch. A description
    that states the condition symmetrically yields no issue.

    Args:
        content: The full rule-file text being written.

    Returns:
        Each drift-issue message, capped at the issue budget.
    """
    if CARDINAL_GATE_ANCHOR not in content:
        return []
    issues: list[str] = []
    for each_pattern in ALL_DIRECTIONAL_PROSE_PATTERNS:
        for each_match in each_pattern.finditer(content):
            if _has_nearby_symmetry_marker(content, each_match):
                continue
            issues.append(_format_issue(each_match.group(0)))
            if len(issues) >= MAX_DIRECTION_ISSUES:
                return issues[:MAX_DIRECTION_ISSUES]
    return issues[:MAX_DIRECTION_ISSUES]


def _has_nearby_symmetry_marker(content: str, located_match: re.Match[str]) -> bool:
    """Return whether a symmetry marker sits within the window around the match.

    A symmetry marker ('differs', 'mismatch', 'both', 'either', 'above and
    below') beside a directional comparator means the prose already conveys that
    a mismatch in either direction trips the gate, so the comparator is not a
    one-directional narrowing.

    Args:
        content: The full rule-file text being inspected.
        located_match: The directional-comparator match to inspect around.

    Returns:
        True when a symmetry marker falls within the window around the match.
    """
    window_start = max(0, located_match.start() - SYMMETRY_WINDOW_RADIUS)
    window_end = located_match.end() + SYMMETRY_WINDOW_RADIUS
    return SYMMETRY_MARKER_PATTERN.search(content[window_start:window_end]) is not None


def _format_issue(matched_phrase: str) -> str:
    """Build one drift-issue message for a matched directional phrase.

    Args:
        matched_phrase: The directional comparator substring the pattern matched.

    Returns:
        The formatted block-reason message for this drift.
    """
    return DIRECTION_MESSAGE_TEMPLATE.format(
        rule_basename=TARGET_RULE_BASENAME, matched_phrase=matched_phrase
    )


def _read_existing_file_content(file_path: str) -> str | None:
    """Return the current on-disk content of file_path, or None when unreadable.

    Args:
        file_path: The path of the file the edit targets.

    Returns:
        The file text, or None when the file is missing or cannot be decoded.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _post_edit_content(tool_name: str, tool_input: dict, file_path: str) -> str | None:
    """Return the content the write or edit would leave on disk, or None.

    For Write the content is the full new payload. For Edit and MultiEdit the
    existing file is read and the replacements applied, so a directional phrase on
    a line the edit does not touch still participates in the check. When the
    existing file cannot be read, None results so the hook stays silent.

    Args:
        tool_name: The intercepted tool -- Write, Edit, or MultiEdit.
        tool_input: The tool input payload.
        file_path: The destination path of the write or edit.

    Returns:
        The reconstructed post-edit content, or None when it cannot be built.
    """
    if tool_name == "Write":
        new_content = tool_input.get("content", "")
        return new_content if isinstance(new_content, str) and new_content else None
    existing_content = _read_existing_file_content(file_path)
    if existing_content is None:
        return None
    return apply_edits(existing_content, edits_for_tool(tool_name, tool_input))


def _build_block_payload(all_issues: list[str]) -> dict:
    """Build the PreToolUse deny payload carrying each directional-drift issue.

    Args:
        all_issues: The drift-issue messages the check produced.

    Returns:
        The hook-result dictionary the harness reads to deny the write.
    """
    reason = " | ".join(all_issues)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": DIRECTION_ADDITIONAL_CONTEXT,
        },
        "systemMessage": DIRECTION_SYSTEM_MESSAGE,
        "suppressOutput": True,
    }


def _emit_hook_decision(decision_payload: dict, target_stream: TextIO) -> None:
    """Write the hook decision JSON to the given output stream.

    Args:
        decision_payload: The hook-result dictionary to serialize.
        target_stream: The stream the harness reads the decision from.
    """
    target_stream.write(json.dumps(decision_payload) + "\n")
    target_stream.flush()


def main() -> None:
    """Read the PreToolUse payload from stdin and block a directional-prose edit."""
    hook_input = read_hook_input_dictionary_from_stdin()
    if hook_input is None:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if not isinstance(tool_name, str) or tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not is_target_rule_file(file_path):
        sys.exit(0)

    post_edit_content = _post_edit_content(tool_name, tool_input, file_path)
    if post_edit_content is None:
        sys.exit(0)

    directional_issues = find_directional_prose_drift(post_edit_content)
    if not directional_issues:
        sys.exit(0)

    block_payload = _build_block_payload(directional_issues)
    log_hook_block(
        calling_hook_name="cardinal_count_prose_direction_blocker.py",
        hook_event="PreToolUse",
        block_reason=block_payload["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name=tool_name,
        offending_input_preview=file_path,
    )
    _emit_hook_decision(block_payload, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
