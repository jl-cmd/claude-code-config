#!/usr/bin/env python3
"""PreToolUse:Write|Edit|MultiEdit hook — blocks plan files that contain an "Open Questions" section.

Plans under `~/.claude/plans/` (or any `.claude/plans/` directory) must not be
written with an unresolved "Open Questions" section. When detected, the agent is
forced to (1) investigate the codebase for answers itself first, then (2) confirm
its interpretations via the AskUserQuestion tool in plain everyday language, and
(3) re-write the plan with the section resolved and removed.
"""

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.open_questions_in_plans_blocker_constants import (  # noqa: E402
    CODE_FENCE_PATTERN,
    INLINE_CODE_PATTERN,
    MARKDOWN_EXTENSION,
    OPEN_QUESTIONS_HEADING_PATTERN,
    PLAN_FILE_ENCODING,
    PLANS_PATH_PREFIX,
    PLANS_PATH_SEGMENT,
)


def _is_markdown_file(file_path: str) -> bool:
    return file_path.lower().endswith(MARKDOWN_EXTENSION)


def _is_inside_plans_directory(file_path: str) -> bool:
    expanded = os.path.expanduser(file_path)
    normalized = os.path.normpath(expanded).replace("\\", "/").lower()
    if PLANS_PATH_SEGMENT in normalized:
        return True
    if normalized.startswith(PLANS_PATH_PREFIX):
        return True
    return False


def _strip_code_regions(text: str) -> str:
    """Remove fenced code blocks and inline code spans so quoted headings don't trigger the regex."""
    without_fences = CODE_FENCE_PATTERN.sub("", text)
    return INLINE_CODE_PATTERN.sub("", without_fences)


def _content_has_open_questions(text: str) -> bool:
    if not text:
        return False
    return bool(OPEN_QUESTIONS_HEADING_PATTERN.search(_strip_code_regions(text)))


def _read_existing_file_text(file_path: str) -> str | None:
    """Return existing file contents, or None when the file is unreadable.

    Narrow exceptions only — FileNotFoundError covers the "first write" case,
    PermissionError covers locked or inaccessible files, and UnicodeDecodeError
    covers binary contents that the markdown scan cannot reason about. Any
    other failure is left to propagate.
    """
    try:
        return Path(file_path).read_text(encoding=PLAN_FILE_ENCODING)
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError, UnicodeDecodeError):
        return None


def _apply_edit_to_text(existing_text: str, old_string: str, new_string: str) -> str:
    """Apply Claude Code's Edit semantics: replace the first occurrence only."""
    return existing_text.replace(old_string, new_string, 1)


def _post_edit_content_for_edit(existing_text: str | None, tool_input: dict) -> str:
    old_string = tool_input.get("old_string", "")
    new_string = tool_input.get("new_string", "")
    safe_old = old_string if isinstance(old_string, str) else ""
    safe_new = new_string if isinstance(new_string, str) else ""
    if existing_text is None:
        return safe_new
    return _apply_edit_to_text(existing_text, safe_old, safe_new)


def _post_edit_content_for_multiedit(existing_text: str | None, tool_input: dict) -> str:
    all_edits = tool_input.get("edits", []) or []
    accumulated_text = existing_text if existing_text is not None else ""
    fallback_new_strings: list[str] = []
    for each_edit in all_edits:
        if not isinstance(each_edit, dict):
            continue
        old_string = each_edit.get("old_string", "")
        new_string = each_edit.get("new_string", "")
        safe_old = old_string if isinstance(old_string, str) else ""
        safe_new = new_string if isinstance(new_string, str) else ""
        accumulated_text = _apply_edit_to_text(accumulated_text, safe_old, safe_new)
        fallback_new_strings.append(safe_new)
    if existing_text is None:
        return "\n".join(fallback_new_strings)
    return accumulated_text


def _extract_candidate_content(tool_name: str, tool_input: dict, file_path: str) -> str:
    if tool_name == "Write":
        content = tool_input.get("content", "")
        return content if isinstance(content, str) else ""
    existing_text = _read_existing_file_text(file_path)
    if tool_name == "Edit":
        return _post_edit_content_for_edit(existing_text, tool_input)
    if tool_name == "MultiEdit":
        return _post_edit_content_for_multiedit(existing_text, tool_input)
    return ""


def _block_reason(file_path: str) -> str:
    return (
        f"BLOCKED: Plan file '{file_path}' contains an 'Open Questions' section. "
        "Open questions in plans are unacceptable — they must be resolved before the plan is saved."
    )


def _block_context() -> str:
    return (
        "An 'Open Questions' section means the plan is not yet ready to commit. Resolve it before retrying:\n\n"
        "1. Investigate the codebase yourself first. For each open question, try to answer it by "
        "reading source files, grepping, or dispatching an Explore agent. Do not skip this step — "
        "always attempt to find the answer before bothering the user.\n\n"
        "2. Confirm interpretations via AskUserQuestion. Once you have a proposed answer or "
        "interpretation for each question, call the AskUserQuestion tool. Phrase the questions in "
        "plain everyday language: state what you found, what you think it means, and ask the user "
        "to confirm or correct. Make it easy to digest and comprehend exactly what you are doing. "
        "Prefer one AskUserQuestion call that covers all open questions where possible.\n\n"
        "3. Re-write the plan. After the user confirms, remove the 'Open Questions' section "
        "entirely and fold the resolved answers into the relevant sections of the plan, then "
        "retry the Write/Edit."
    )


def _block_system_message() -> str:
    return (
        "Plan blocked — 'Open Questions' must be resolved (investigate the codebase, then confirm "
        "interpretations via AskUserQuestion in plain language) before saving."
    )


def _emit_hook_result(payload: dict, output_stream: TextIO) -> None:
    output_stream.write(json.dumps(payload) + "\n")
    output_stream.flush()


def main() -> None:
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

    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        sys.exit(0)

    if not _is_markdown_file(file_path):
        sys.exit(0)

    if not _is_inside_plans_directory(file_path):
        sys.exit(0)

    candidate_content = _extract_candidate_content(tool_name, tool_input, file_path)
    if not _content_has_open_questions(candidate_content):
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


if __name__ == "__main__":
    main()
