"""Tests for open_questions_in_plans_blocker hook."""

import json
import os
import subprocess
import sys


HOOK_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "open_questions_in_plans_blocker.py"
)

_plan_with_open_questions = (
    "## Context\nA plan.\n\n## Open Questions\n- Which auth provider?\n"
)
_plan_without_open_questions = "## Context\nA plan.\n\n## Approach\nDo the thing.\n"


class _RunHook:
    def __call__(
        self, tool_name: str, tool_input: dict
    ) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )


_run_hook = _RunHook()


def test_blocks_write_plan_with_open_questions_heading():
    result = _run_hook(
        "Write",
        {
            "file_path": os.path.expanduser("~/.claude/plans/add-feature.md"),
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Open Questions" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_blocks_edit_plan_adding_open_questions():
    result = _run_hook(
        "Edit",
        {
            "file_path": os.path.expanduser("~/.claude/plans/refactor.md"),
            "old_string": "## Approach\nDo it.",
            "new_string": "## Approach\nDo it.\n\n## Open Questions\n- Which DB?",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_project_local_plans_directory():
    """Project-local `.claude/plans/` paths are also covered."""
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/my-plan.md",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_case_insensitive_heading():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": "# open questions\n- foo\n",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_bold_open_questions_heading():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": "**Open Questions**\n- foo\n",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_plan_without_open_questions():
    result = _run_hook(
        "Write",
        {
            "file_path": os.path.expanduser("~/.claude/plans/clean.md"),
            "content": _plan_without_open_questions,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_open_questions_prose_outside_heading():
    """A plan that merely mentions 'open questions' in prose, not as a heading, is fine."""
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": "## Context\nThere are no open questions left.\n",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_md_file_outside_plans_directory():
    """An `Open Questions` section in a non-plan .md file is not this hook's concern."""
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/notes.md",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_non_markdown_file_in_plans_directory():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/notes.txt",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_unknown_tool():
    result = _run_hook(
        "Grep",
        {"pattern": "foo", "path": "."},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_empty_file_path():
    result = _run_hook(
        "Write",
        {"file_path": "", "content": _plan_with_open_questions},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_json_decode_error():
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_non_dict_stdin():
    payload = json.dumps(["not", "a", "dict"])
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_denial_carries_system_message_and_context():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["suppressOutput"] is True
    assert isinstance(output["systemMessage"], str) and output["systemMessage"]
    additional_context = output["hookSpecificOutput"]["additionalContext"]
    assert "AskUserQuestion" in additional_context
    assert "investigate" in additional_context.lower()


def test_edit_without_open_questions_in_new_string_passes():
    result = _run_hook(
        "Edit",
        {
            "file_path": ".claude/plans/x.md",
            "old_string": "## Open Questions\n- foo",
            "new_string": "## Resolved\n- foo is bar",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_windows_style_plans_path():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude\\plans\\my-plan.md",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
