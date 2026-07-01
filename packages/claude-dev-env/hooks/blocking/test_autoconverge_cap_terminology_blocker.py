"""Behavioral tests for the autoconverge cap-terminology PreToolUse blocker."""

import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking.autoconverge_cap_terminology_blocker import (  # noqa: E402
    evaluate,
    find_cap_terminology_violations,
)

AUTOCONVERGE_DOC_PATH = "packages/claude-dev-env/skills/autoconverge/reference/convergence.md"
UNRELATED_DOC_PATH = "packages/claude-dev-env/skills/pr-converge/reference/loop.md"


def test_poll_cap_phrase_is_flagged() -> None:
    all_violations = find_cap_terminology_violations(
        "poll up to the configured cap; no review after the poll cap"
    )
    assert "poll cap" in all_violations


def test_bare_after_the_cap_is_flagged() -> None:
    all_violations = find_cap_terminology_violations("surfaces no review at all after the cap")
    assert "after the cap" in all_violations


def test_configured_cap_wording_is_clean() -> None:
    all_violations = find_cap_terminology_violations(
        "poll up to the configured cap, then after the configured cap bypass the gate"
    )
    assert all_violations == []


def test_evaluate_denies_poll_cap_in_autoconverge_markdown() -> None:
    deny_reason = evaluate(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": AUTOCONVERGE_DOC_PATH,
                "content": "no review after the poll cap",
            },
        }
    )
    assert deny_reason is not None
    assert "configured cap" in deny_reason


def test_evaluate_ignores_poll_cap_outside_autoconverge_skill() -> None:
    deny_reason = evaluate(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": UNRELATED_DOC_PATH,
                "content": "no review after the poll cap",
            },
        }
    )
    assert deny_reason is None


def test_evaluate_allows_configured_cap_in_autoconverge_markdown() -> None:
    deny_reason = evaluate(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": AUTOCONVERGE_DOC_PATH,
                "new_string": "no review after the configured cap",
            },
        }
    )
    assert deny_reason is None


def test_evaluate_ignores_poll_cap_inside_code_fence() -> None:
    fenced_body = "```\nno review after the poll cap\n```"
    deny_reason = evaluate(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": AUTOCONVERGE_DOC_PATH,
                "content": fenced_body,
            },
        }
    )
    assert deny_reason is None
