#!/usr/bin/env python3
"""PreToolUse hook: blocks autoconverge doc writes that use inconsistent cap terminology.

The autoconverge skill names the Copilot review-poll limit "configured cap". This
hook denies a Write/Edit/MultiEdit to an autoconverge markdown surface that spells
that limit "poll cap" or as a bare "after the cap", so every autoconverge doc
reads one term for the limit.
"""

import json
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.autoconverge_cap_terminology_constants import (  # noqa: E402
    ALL_CAP_TERMINOLOGY_PATTERNS,
    ALL_MARKDOWN_EXTENSIONS,
    ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    AUTOCONVERGE_SKILL_PATH_MARKER,
    CODE_FENCE_PATTERN,
    DENY_ADDITIONAL_CONTEXT,
    DENY_SYSTEM_MESSAGE,
    INLINE_CODE_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin  # noqa: E402


def _is_autoconverge_markdown(file_path: str) -> bool:
    """Report whether a path is a markdown file inside the autoconverge skill.

    Args:
        file_path: The target file path from the tool payload.

    Returns:
        True when the path sits under the autoconverge skill directory and ends
        with a markdown extension, False otherwise.
    """
    normalized_path = file_path.replace("\\", "/").lower()
    if AUTOCONVERGE_SKILL_PATH_MARKER not in normalized_path:
        return False
    return Path(file_path).suffix.lower() in ALL_MARKDOWN_EXTENSIONS


def find_cap_terminology_violations(text: str) -> list[str]:
    """Return the inconsistent cap-terminology phrases found in markdown text.

    Strips fenced and inline code so a code sample carrying the phrase does not
    trip the gate, then matches each inconsistent-terminology pattern.

    Args:
        text: The markdown text to scan.

    Returns:
        The lowercased phrases matched, one per pattern that fired, empty when
        the text uses only the canonical term.
    """
    scan_text = CODE_FENCE_PATTERN.sub("", text)
    scan_text = INLINE_CODE_PATTERN.sub("", scan_text)
    if not scan_text.strip():
        return []
    all_detected: list[str] = []
    for each_pattern in ALL_CAP_TERMINOLOGY_PATTERNS:
        all_matches = each_pattern.findall(scan_text)
        if all_matches:
            all_detected.append(all_matches[0].strip().lower())
    return all_detected


def _extract_written_text(tool_name: str, input_by_key: dict[str, object]) -> str:
    """Return the text a Write, Edit, or MultiEdit payload would write.

    Args:
        tool_name: The tool name from the payload.
        input_by_key: The tool_input mapping from the payload.

    Returns:
        The written content for a Write, the new_string for an Edit, or every
        edit's new_string joined for a MultiEdit; empty when none is present.
    """
    if tool_name == "Write":
        raw_content = input_by_key.get("content", "")
        return raw_content if isinstance(raw_content, str) else ""
    if tool_name == "Edit":
        raw_new_string = input_by_key.get("new_string", "")
        return raw_new_string if isinstance(raw_new_string, str) else ""
    raw_edits = input_by_key.get("edits", [])
    if not isinstance(raw_edits, list):
        return ""
    all_new_strings: list[str] = []
    for each_edit in raw_edits:
        if not isinstance(each_edit, dict):
            continue
        new_string = each_edit.get("new_string", "")
        if isinstance(new_string, str):
            all_new_strings.append(new_string)
    return "\n".join(all_new_strings)


def _build_deny_reason(file_path: str, all_detected_phrases: list[str]) -> str:
    """Build the permissionDecisionReason text for a terminology denial.

    Args:
        file_path: The target file the violation was found in.
        all_detected_phrases: The inconsistent phrases the scan matched.

    Returns:
        The deny-reason text naming the file, the phrases, and the canonical term.
    """
    formatted = ", ".join(f'"{each_phrase}"' for each_phrase in all_detected_phrases)
    return (
        f"Inconsistent cap terminology in {file_path}: {formatted}. "
        f"The autoconverge skill names the Copilot review-poll limit "
        f"'configured cap' — use that term."
    )


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether a payload writes inconsistent cap terminology.

    Applies the tool-name gate, the autoconverge-markdown path gate, the written
    text extraction, and the terminology scan the standalone hook applies.

    Args:
        payload_by_key: The PreToolUse payload with tool_name and tool_input.

    Returns:
        The deny-reason text when the write is denied, or None to allow.
    """
    raw_tool_name = payload_by_key.get("tool_name", "")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    if tool_name not in ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES:
        return None

    raw_tool_input = payload_by_key.get("tool_input", {})
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return None
    if not _is_autoconverge_markdown(file_path):
        return None

    written_text = _extract_written_text(tool_name, tool_input)
    if not written_text:
        return None

    all_detected_phrases = find_cap_terminology_violations(written_text)
    if not all_detected_phrases:
        return None

    return _build_deny_reason(file_path, all_detected_phrases)


def _build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the full deny payload the hook serializes to stdout.

    Args:
        deny_reason: The permissionDecisionReason text for the denial.

    Returns:
        The deny payload dictionary carrying the decision, guidance, and system
        message.
    """
    log_hook_block(
        calling_hook_name="autoconverge_cap_terminology_blocker.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
            "additionalContext": DENY_ADDITIONAL_CONTEXT,
        },
        "systemMessage": DENY_SYSTEM_MESSAGE,
        "suppressOutput": True,
    }


def _emit_hook_result(all_hook_data: dict[str, object], output_stream: TextIO) -> None:
    """Write the hook result JSON to the given output stream.

    Args:
        all_hook_data: The hook result payload to serialize.
        output_stream: The stream to write the serialized payload to.
    """
    output_stream.write(json.dumps(all_hook_data) + "\n")
    output_stream.flush()


def main() -> None:
    """Read the PreToolUse payload from stdin and emit a deny when it violates."""
    payload_dictionary = read_hook_input_dictionary_from_stdin()
    if payload_dictionary is None:
        sys.exit(0)

    deny_reason = evaluate(payload_dictionary)
    if deny_reason is None:
        sys.exit(0)

    _emit_hook_result(_build_deny_payload(deny_reason), sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
