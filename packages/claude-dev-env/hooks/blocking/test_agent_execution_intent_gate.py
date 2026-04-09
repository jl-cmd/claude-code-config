"""Tests for agent-execution-intent-gate hook."""

import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).parent / "agent-execution-intent-gate.py"


def _run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def test_allows_task_without_agent_prompt_handoff() -> None:
    payload = {
        "tool_name": "Task",
        "tool_input": {"prompt": "run the workflow", "description": "delegate"},
    }
    result = _run_hook(payload)
    assert result.stdout.strip() == ""


def test_allows_agent_prompt_with_scope_anchors() -> None:
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "prompt": (
                "/agent-prompt\n"
                "target_local_roots\n"
                "target_canonical_roots\n"
                "target_file_globs\n"
                "comparison_basis\n"
                "completion_boundary\n"
            ),
            "description": "delegate",
        },
    }
    result = _run_hook(payload)
    assert result.stdout.strip() == ""


def test_denies_agent_prompt_when_scope_anchors_missing() -> None:
    payload = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "/agent-prompt\ntarget_local_roots only",
            "description": "delegate",
        },
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Scope anchors missing" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_allows_agent_prompt_in_description_with_anchors() -> None:
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "description": "/agent-prompt delegation",
            "prompt": (
                "target_local_roots\n"
                "target_canonical_roots\n"
                "target_file_globs\n"
                "comparison_basis\n"
                "completion_boundary\n"
            ),
        },
    }
    result = _run_hook(payload)
    assert result.stdout.strip() == ""
