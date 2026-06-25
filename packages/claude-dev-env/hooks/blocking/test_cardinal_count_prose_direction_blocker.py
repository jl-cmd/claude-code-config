"""Tests for cardinal_count_prose_direction_blocker hook."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cardinal_count_prose_direction_blocker import (
    find_directional_prose_drift,
    is_target_rule_file,
)

from hooks_constants.cardinal_count_prose_direction_blocker_constants import (
    DIRECTION_SYSTEM_MESSAGE,
    TARGET_RULE_BASENAME,
)

HOOK_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "cardinal_count_prose_direction_blocker.py"
)

CARDINAL_GATE_REFERENCE = "`check_docstring_cardinal_count_matches_constant_family`"

DRIFT_BELOW_RULE_TEXT = (
    f"The {CARDINAL_GATE_REFERENCE} gate blocks this drift -- a cardinal-count "
    "docstring that names two or more members of a referenced constant family, "
    "leaves at least one referenced member out, and states a count below the "
    "family size -- at Write/Edit time, on test modules as well as production "
    "modules.\n"
)

DRIFT_MORE_MEMBERS_RULE_TEXT = (
    f"{CARDINAL_GATE_REFERENCE} covers a docstring that states a cardinal count "
    "of an outcome family and lists those members, while the module references "
    "more members of the same constant family than the count names.\n"
)

SYMMETRIC_DIFFERS_RULE_TEXT = (
    f"The {CARDINAL_GATE_REFERENCE} gate blocks this drift -- a cardinal-count "
    "docstring that names two or more members of a referenced constant family, "
    "leaves at least one referenced member out, and states a count that differs "
    "from the family size -- at Write/Edit time.\n"
)

BOTH_DIRECTIONS_RULE_TEXT = (
    f"The {CARDINAL_GATE_REFERENCE} gate fires when a stated count is above the "
    "family size and a count below it both trip the gate.\n"
)

NO_ANCHOR_RULE_TEXT = (
    "Some other gate fires when a stated count is below the family size, but "
    "this prose never names the cardinal-count gate by its function name.\n"
)


class _RunHook:
    """Helper to drive the hook via subprocess, mirroring the sibling test style."""

    def __call__(self, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )


_run_hook = _RunHook()


def _target_rule_path(tmp_path: Path) -> Path:
    """Return a path inside tmp_path named after the guarded rule basename."""
    return tmp_path / TARGET_RULE_BASENAME


def should_flag_target_rule_basename() -> None:
    assert is_target_rule_file("/somewhere/" + TARGET_RULE_BASENAME) is True


def should_ignore_unrelated_markdown_file() -> None:
    assert is_target_rule_file("/somewhere/other-rule.md") is False


def should_flag_a_count_below_the_family_size() -> None:
    issues = find_directional_prose_drift(DRIFT_BELOW_RULE_TEXT)
    assert len(issues) == 1
    assert "below the family size" in issues[0]


def should_flag_more_members_than_the_count_names() -> None:
    issues = find_directional_prose_drift(DRIFT_MORE_MEMBERS_RULE_TEXT)
    assert len(issues) == 1
    assert "than the count names" in issues[0]


def should_allow_symmetric_differs_phrasing() -> None:
    assert find_directional_prose_drift(SYMMETRIC_DIFFERS_RULE_TEXT) == []


def should_allow_a_description_that_names_both_directions() -> None:
    assert find_directional_prose_drift(BOTH_DIRECTIONS_RULE_TEXT) == []


def should_ignore_directional_phrasing_without_the_cardinal_gate_anchor() -> None:
    assert find_directional_prose_drift(NO_ANCHOR_RULE_TEXT) == []


def should_deny_a_write_that_introduces_directional_phrasing() -> None:
    completed = _run_hook(
        "Write",
        {
            "file_path": "/anywhere/" + TARGET_RULE_BASENAME,
            "content": DRIFT_BELOW_RULE_TEXT,
        },
    )
    parsed_output = json.loads(completed.stdout)
    hook_specific = parsed_output["hookSpecificOutput"]
    assert hook_specific["permissionDecision"] == "deny"
    assert parsed_output["systemMessage"] == DIRECTION_SYSTEM_MESSAGE


def should_allow_a_write_with_symmetric_phrasing() -> None:
    completed = _run_hook(
        "Write",
        {
            "file_path": "/anywhere/" + TARGET_RULE_BASENAME,
            "content": SYMMETRIC_DIFFERS_RULE_TEXT,
        },
    )
    assert completed.stdout.strip() == ""


def should_allow_a_write_to_an_unrelated_markdown_file() -> None:
    completed = _run_hook(
        "Write",
        {"file_path": "/anywhere/other-rule.md", "content": DRIFT_BELOW_RULE_TEXT},
    )
    assert completed.stdout.strip() == ""


def should_deny_an_edit_that_introduces_directional_phrasing(tmp_path: Path) -> None:
    rule_path = _target_rule_path(tmp_path)
    rule_path.write_text(SYMMETRIC_DIFFERS_RULE_TEXT, encoding="utf-8")
    completed = _run_hook(
        "Edit",
        {
            "file_path": str(rule_path),
            "old_string": "a count that differs from the family size",
            "new_string": "a count below the family size",
        },
    )
    parsed_output = json.loads(completed.stdout)
    assert parsed_output["hookSpecificOutput"]["permissionDecision"] == "deny"


def should_allow_an_edit_that_keeps_symmetric_phrasing(tmp_path: Path) -> None:
    rule_path = _target_rule_path(tmp_path)
    rule_path.write_text(SYMMETRIC_DIFFERS_RULE_TEXT, encoding="utf-8")
    completed = _run_hook(
        "Edit",
        {
            "file_path": str(rule_path),
            "old_string": "at Write/Edit time.",
            "new_string": "at Write or Edit time.",
        },
    )
    assert completed.stdout.strip() == ""
