"""Tests for state_description_blocker hook."""

import json
import os
import subprocess
import sys

HOOK_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "state_description_blocker.py"
)

CLEAN_PYTHON = "x = 1  # Uses a default timeout"
CLEAN_MD = "# Config\n\nThe API uses port 8080."
CLEAN_COMMENT = "# Configured with a 30-second timeout"

VIOLATION_INSTEAD_OF_COMMENT = "# Uses X instead of Y"
VIOLATION_PREVIOUSLY_COMMENT = "# Previously configured via Z"
VIOLATION_NOW_USES_COMMENT = "# Now uses the new API client"
VIOLATION_COMMENT_WITH_CLOSE_BLOCK = "# No longer functional — the */ route was deprecated"
VIOLATION_MD_INSTEAD = "# API\n\nUses GraphQL instead of REST."
VIOLATION_MD_PREVIOUSLY = "# Config\n\nPreviously set via env var."
VIOLATION_MD_NOW_USES = "# Auth\n\nNow uses OAuth2."


def _run_hook(tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )


def test_block_clean_python_comment_passes():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": CLEAN_PYTHON,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_clean_markdown_passes():
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/README.md",
            "content": CLEAN_MD,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_clean_comment_passes():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": CLEAN_COMMENT,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_irrelevant_file_passes():
    result = _run_hook(
        "Write",
        {
            "file_path": "data.txt",
            "content": VIOLATION_INSTEAD_OF_COMMENT,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_empty_content_passes():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": "",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_block_unknown_tool_passes():
    result = _run_hook(
        "Grep",
        {
            "pattern": "foo",
            "path": ".",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_detects_instead_of_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": VIOLATION_INSTEAD_OF_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "instead of" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_previously_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": VIOLATION_PREVIOUSLY_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "previously" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_now_uses_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/client.ts",
            "content": VIOLATION_NOW_USES_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "now uses" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_instead_of_in_markdown():
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/api.md",
            "content": VIOLATION_MD_INSTEAD,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_detects_previously_in_markdown():
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/config.md",
            "content": VIOLATION_MD_PREVIOUSLY,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_detects_now_uses_in_markdown():
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/auth.md",
            "content": VIOLATION_MD_NOW_USES,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_detects_edit_new_string():
    result = _run_hook(
        "Edit",
        {
            "file_path": "src/main.py",
            "old_string": "old_comment",
            "new_string": VIOLATION_PREVIOUSLY_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "previously" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_clean_edit_passes():
    result = _run_hook(
        "Edit",
        {
            "file_path": "src/main.py",
            "old_string": "x = 1",
            "new_string": CLEAN_PYTHON,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_system_message_and_suppress_output():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": VIOLATION_INSTEAD_OF_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["suppressOutput"] is True
    assert isinstance(output["systemMessage"], str)
    assert len(output["systemMessage"]) > 0


def test_detects_no_longer_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": "# No longer supports legacy mode",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no longer" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_used_to_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": "# Used to be hardcoded",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "used to" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_switched_to_in_comment():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": "# Switched to async processing",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "switched to" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_comment_with_close_block_token():
    """A single-line # comment containing */ (e.g. docs referencing a deprecated */ route)
    should still be scanned for violations — the `*/` must not trigger a spurious
    block-comment `continue` that skips the single-line comment check.
    Real pattern: midjourney-docs 'no longer works' + route path with */."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/config.py",
            "content": VIOLATION_COMMENT_WITH_CLOSE_BLOCK,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no longer" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_detects_inline_trailing_comment():
    """A code line with a trailing inline comment containing historical language should
    be blocked. Real pattern: ARCHITECTURE.md 'no longer needed' reference in migration
    context — simulates `x = val  # previously needed but now handled elsewhere`."""
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": "max_retries = 3  # No longer needed since async retry handles it",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no longer" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_additional_context_contains_examples():
    result = _run_hook(
        "Write",
        {
            "file_path": "src/main.py",
            "content": VIOLATION_INSTEAD_OF_COMMENT,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    ctx = output["hookSpecificOutput"].get("additionalContext", "")
    assert "BAD:" in ctx
    assert "GOOD:" in ctx
