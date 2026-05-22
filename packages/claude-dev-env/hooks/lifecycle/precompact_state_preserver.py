#!/usr/bin/env python3
"""PreCompact hook: emit a focus directive that preserves stateful-skill pointers.

When Claude Code fires ``PreCompact`` (manual via ``/compact`` or auto when the
context window is near full), this hook scans a small registry of known
state-file locations for stateful skills such as ``pr-converge``, ``bugteam``,
and ``/loop``. When a state file is found, the hook prints a templated focus
directive to stdout. Per the PreCompact spec, the directive is appended to the
compactor LLM's custom_instructions so the summary preserves load-bearing
pointers (state-file path, current_head SHA, worktree path, phase, operator
follow-ups) and explicitly drops verbose chaff (per-finding bodies, stale
SHAs, thread IDs, per-tick narrations).

The hook is templating-only — it does not synthesize prose. The compactor LLM
remains the only thing that writes the actual summary. The hook only injects
structured guidance that scales with how richly the skill's state file is
populated.

Behavior contract:
    - Always exits with the success code. PreCompact's blocking exit code
      would halt compaction; this hook is advisory.
    - When stdin is malformed, no state file is found, or every state file
      is unreadable, the hook prints nothing and exits clean — compaction
      proceeds with default behavior.
    - When ``trigger == "manual"`` and ``custom_instructions`` is non-empty,
      the operator's own instructions are echoed first; this hook's
      directive is appended below, never replacing operator intent.

Sources:
    - https://code.claude.com/docs/en/hooks (PreCompact event spec)
    - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
    - https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.precompact_state_preserver_constants import (  # noqa: E402
    CLAUDE_JOB_DIR_ENV_VAR,
    DIRECTIVE_DROP_HEADING,
    DIRECTIVE_HEADER,
    DIRECTIVE_PRESERVE_HEADING,
    DIRECTIVE_RESUMPTION_HEADING,
    DROP_LIST_LINES,
    HOOK_EVENT_NAME_PRECOMPACT,
    JOB_DIR_STATE_FILENAMES,
    MAX_OPERATOR_FOLLOWUPS_RENDERED,
    MAX_STATE_FILE_BYTES,
    PRESERVE_FIELDS_ORDERED,
    PROJECT_STATE_DIRECTORY_FRAGMENT,
    PROJECT_STATE_GLOB_PATTERN,
    STATE_FILE_FIELD_OPERATOR_FOLLOWUPS,
    TRIGGER_MANUAL,
)


def _candidate_state_paths(payload_cwd: str) -> list[Path]:
    """Enumerate every state-file path that the registry knows about.

    The order is deterministic so test assertions and operator inspection
    are stable: ``$CLAUDE_JOB_DIR`` entries first (oldest convention), then
    project-local ``.claude/state/*.json`` entries.

    Args:
        payload_cwd: The ``cwd`` value carried in the PreCompact stdin
            payload, used to anchor the project-local scan. An empty
            string skips the project-local scan entirely.

    Returns:
        Ordered list of absolute ``Path`` candidates. The list is not
        filtered by existence; the caller checks each path.
    """
    candidate_paths: list[Path] = []
    job_directory = os.environ.get(CLAUDE_JOB_DIR_ENV_VAR, "").strip()
    if job_directory:
        job_directory_path = Path(job_directory)
        for each_filename in JOB_DIR_STATE_FILENAMES:
            candidate_paths.append(job_directory_path / each_filename)
    if payload_cwd:
        project_state_directory = Path(payload_cwd) / PROJECT_STATE_DIRECTORY_FRAGMENT
        if project_state_directory.is_dir():
            for each_file in sorted(project_state_directory.glob(PROJECT_STATE_GLOB_PATTERN)):
                candidate_paths.append(each_file)
    return candidate_paths


def _load_state_file(state_path: Path) -> dict[str, object] | None:
    """Load and parse a state file, returning None on any failure.

    State files larger than ``MAX_STATE_FILE_BYTES`` are skipped to keep
    the hook's own footprint bounded; the directive emits at most a few
    hundred tokens regardless of state-file size.

    Args:
        state_path: Absolute path to the state JSON file.

    Returns:
        Parsed mapping when the file exists, is under the size cap, and
        decodes as a JSON object; ``None`` otherwise.
    """
    try:
        file_size_bytes = state_path.stat().st_size
    except OSError:
        return None
    if file_size_bytes > MAX_STATE_FILE_BYTES:
        return None
    try:
        decoded_payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(decoded_payload, dict):
        return None
    return decoded_payload


def _render_field_line(field_name: str, field_value: object) -> str | None:
    """Render one preserve-field bullet, or None when the field is empty.

    The ``operator_followups`` field is rendered as a multi-line block;
    every other field renders as a single ``- field: value`` bullet.

    Args:
        field_name: One of the keys in ``PRESERVE_FIELDS_ORDERED``.
        field_value: The value pulled from the loaded state mapping.

    Returns:
        A markdown-style bullet (or multi-line block) ready to splice into
        the directive body; ``None`` when the field is missing, ``None``,
        or an empty string/list.
    """
    if field_value is None:
        return None
    if field_name == STATE_FILE_FIELD_OPERATOR_FOLLOWUPS:
        if not isinstance(field_value, list) or not field_value:
            return None
        rendered_followups = [
            f"    - {str(each_item)}" for each_item in field_value[:MAX_OPERATOR_FOLLOWUPS_RENDERED]
        ]
        return f"- {field_name}:\n" + "\n".join(rendered_followups)
    rendered_value = str(field_value).strip()
    if rendered_value == "":
        return None
    return f"- {field_name}: {rendered_value}"


def _render_directive(state_path: Path, all_state_fields: dict[str, object]) -> str:
    """Render the full focus directive for one matched state file.

    Args:
        state_path: Absolute path to the matched state file. Echoed
            verbatim into the directive so the compactor preserves it as
            a re-load pointer for the next session.
        all_state_fields: Decoded state mapping. Only the fields named in
            ``PRESERVE_FIELDS_ORDERED`` are rendered; everything else is
            ignored.

    Returns:
        The directive as a single string with embedded newlines, ready
        to print to stdout.
    """
    directive_lines: list[str] = [DIRECTIVE_HEADER, "", DIRECTIVE_PRESERVE_HEADING]
    directive_lines.append(f"- state_file_path: {state_path.as_posix()}")
    for each_field in PRESERVE_FIELDS_ORDERED:
        rendered_line = _render_field_line(each_field, all_state_fields.get(each_field))
        if rendered_line is not None:
            directive_lines.append(rendered_line)
    directive_lines.append("")
    directive_lines.append(DIRECTIVE_DROP_HEADING)
    for each_drop_line in DROP_LIST_LINES:
        directive_lines.append(f"- {each_drop_line}")
    directive_lines.append("")
    directive_lines.append(DIRECTIVE_RESUMPTION_HEADING)
    directive_lines.append(
        f"Re-read {state_path.as_posix()} on resumption to recover full skill state."
    )
    return "\n".join(directive_lines)


def _first_matching_state(payload_cwd: str) -> tuple[Path, dict[str, object]] | None:
    """Walk the candidate registry and return the first loadable state file.

    Args:
        payload_cwd: ``cwd`` from the PreCompact stdin payload.

    Returns:
        The matching path and its parsed mapping, or ``None`` when no
        candidate exists or loads cleanly.
    """
    for each_candidate in _candidate_state_paths(payload_cwd):
        loaded_state = _load_state_file(each_candidate)
        if loaded_state is not None:
            return each_candidate, loaded_state
    return None


def _echo_operator_instructions(payload_by_field: dict[str, object]) -> str:
    """Return the operator's manual ``custom_instructions``, or an empty string.

    Per the PreCompact spec, manual ``/compact`` invocations may include a
    ``custom_instructions`` payload field that the user typed at the prompt.
    The hook echoes that string first so the operator's stated intent leads
    the directive and the templated guidance follows, never replacing it.

    Args:
        payload_by_field: Decoded PreCompact stdin payload.

    Returns:
        The operator's instructions plus a trailing blank line when both
        ``trigger == "manual"`` and ``custom_instructions`` is a non-empty
        string; an empty string otherwise.
    """
    if payload_by_field.get("trigger", "") != TRIGGER_MANUAL:
        return ""
    raw_instructions = payload_by_field.get("custom_instructions", "")
    if not isinstance(raw_instructions, str):
        return ""
    stripped_instructions = raw_instructions.strip()
    if stripped_instructions == "":
        return ""
    return f"{stripped_instructions}\n\n"


def _emit_directive(directive_body: str, output_stream: TextIO) -> None:
    """Write the rendered focus directive to the provided stream.

    Args:
        directive_body: The full directive text (operator prefix plus the
            rendered template), ready to emit with a trailing newline.
        output_stream: Writable text stream — production code passes
            ``sys.stdout``; tests pass a ``StringIO`` to capture output.
    """
    output_stream.write(f"{directive_body}\n")
    output_stream.flush()


def main(input_stream: TextIO, output_stream: TextIO) -> None:
    """Hook entry point. Reads stdin, scans the registry, writes the directive.

    Always returns clean. Any failure path (malformed stdin, no state file,
    every state file unreadable) results in zero stdout — compaction
    proceeds with the default behavior.

    Args:
        input_stream: Readable text stream carrying the PreCompact JSON
            payload — production code passes ``sys.stdin``; tests pass a
            ``StringIO`` containing the synthetic payload.
        output_stream: Writable text stream where the directive lands —
            production code passes ``sys.stdout``; tests pass a
            ``StringIO`` to capture output.
    """
    try:
        hook_payload = json.load(input_stream)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(hook_payload, dict):
        return
    if hook_payload.get("hook_event_name", "") != HOOK_EVENT_NAME_PRECOMPACT:
        return
    payload_cwd = hook_payload.get("cwd", "")
    if not isinstance(payload_cwd, str):
        payload_cwd = ""
    matched_state = _first_matching_state(payload_cwd)
    if matched_state is None:
        return
    state_path, all_state_fields = matched_state
    operator_prefix = _echo_operator_instructions(hook_payload)
    directive_text = _render_directive(state_path, all_state_fields)
    _emit_directive(f"{operator_prefix}{directive_text}", output_stream)


if __name__ == "__main__":
    main(sys.stdin, sys.stdout)
