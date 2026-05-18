#!/usr/bin/env python3
"""PreToolUse hook: record formal bugteam Skill invocations into pr-converge state.

Companion to ``pr_converge_bugteam_enforcer``. On every
``Skill({skill: "bugteam"})`` invocation, this hook stamps the pr-converge
state.json with ``bugteam_skill_invoked_at_head = current_head`` and
``bugteam_skill_invoked_at_tick = tick_count`` so the enforcer can confirm
the formal Skill fired this tick at the current HEAD before allowing any
follow-on clean-coder audit-shaped Agent spawn.

``qbug`` invocations are deliberately ignored — qbug is not an accepted
substitute for the formal bugteam Skill at Step 5.

The hook never blocks: it returns exit 0 in every branch so the Skill call
proceeds unchanged.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.pr_converge_bugteam_enforcer_constants import (
    BUGTEAM_SKILL_NAME,
    SKILL_TOOL_NAME,
    STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_HEAD,
    STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_TICK,
    STATE_FIELD_CURRENT_HEAD,
    STATE_FIELD_TICK_COUNT,
    STATE_FILE_ATOMIC_WRITE_SUFFIX,
    STATE_FILE_JSON_INDENT_SPACES,
)
from config.pr_converge_bugteam_enforcer_state import (
    _load_state_dictionary,
    _resolve_state_path,
)


def _atomic_write_state(state_path: Path, state_by_field: dict[str, object]) -> None:
    """Serialize state to disk atomically via tempfile + rename.

    Args:
        state_path: Destination ``pr-converge-state.json`` path.
        state_by_field: Updated state mapping each field name to its value.
    """
    parent_directory = state_path.parent
    parent_directory.mkdir(parents=True, exist_ok=True)
    encoded_text = json.dumps(state_by_field, indent=STATE_FILE_JSON_INDENT_SPACES, sort_keys=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(parent_directory),
        delete=False,
        suffix=STATE_FILE_ATOMIC_WRITE_SUFFIX,
    ) as temporary_handle:
        temporary_handle.write(encoded_text)
        temporary_path = Path(temporary_handle.name)
    os.replace(str(temporary_path), str(state_path))


def _record_bugteam_skill_invocation(state_by_field: dict[str, object]) -> dict[str, object]:
    """Return a copy of state with bugteam-Skill invocation fields stamped.

    Args:
        state_by_field: Existing pr-converge state mapping each field name to
            its value.

    Returns:
        New dictionary identical to ``state_by_field`` plus
        ``bugteam_skill_invoked_at_head`` set to ``current_head`` and
        ``bugteam_skill_invoked_at_tick`` set to ``tick_count``.
    """
    updated_state = dict(state_by_field)
    updated_state[STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_HEAD] = state_by_field.get(STATE_FIELD_CURRENT_HEAD)
    updated_state[STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_TICK] = state_by_field.get(STATE_FIELD_TICK_COUNT)
    return updated_state


def _is_formal_bugteam_skill_invocation(payload_by_field: dict[str, object]) -> bool:
    """Return True when this hook invocation matches the formal bugteam Skill.

    Args:
        payload_by_field: The full PreToolUse hook payload (already JSON-parsed),
            keyed by top-level field name.

    Returns:
        True when ``tool_name == "Skill"`` and ``tool_input["skill"]
        == "bugteam"``. Returns False for qbug and every other skill.
    """
    if payload_by_field.get("tool_name", "") != SKILL_TOOL_NAME:
        return False
    tool_input = payload_by_field.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return False
    return tool_input.get("skill", "") == BUGTEAM_SKILL_NAME


def main() -> None:
    try:
        hook_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    if not isinstance(hook_payload, dict):
        sys.exit(0)
    if not _is_formal_bugteam_skill_invocation(hook_payload):
        sys.exit(0)
    state_path = _resolve_state_path()
    if state_path is None:
        sys.exit(0)
    parsed_state = _load_state_dictionary(state_path)
    if parsed_state is None:
        sys.exit(0)
    updated_state = _record_bugteam_skill_invocation(parsed_state)
    try:
        _atomic_write_state(state_path, updated_state)
    except OSError:
        sys.exit(0)
    sys.exit(0)


if __name__ == "__main__":
    main()
