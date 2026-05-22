"""Tests for the ``precompact_state_preserver`` PreCompact hook.

Exercises the hook end-to-end via subprocess: synthesizes a PreCompact
stdin payload, places a fake state file in a tempdir, points
``$CLAUDE_JOB_DIR`` at the tempdir, runs the hook, and asserts the
templated stdout contains the expected pointer, drop-list, and
resumption-hint lines.

Test files are exempt from the no-inline-comments rule per CODE_RULES.md.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HOOK_PATH = Path(__file__).parent / "precompact_state_preserver.py"


def _run_hook(
    payload: dict[str, Any], extra_env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **extra_env}
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _write_state_file(directory: Path, filename: str, body: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    target.write_text(json.dumps(body), encoding="utf-8")
    return target


def _precompact_payload(
    cwd: str, trigger: str, custom_instructions: str
) -> dict[str, Any]:
    return {
        "session_id": "test-session",
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": cwd,
        "permission_mode": "default",
        "hook_event_name": "PreCompact",
        "trigger": trigger,
        "custom_instructions": custom_instructions,
    }


def test_emits_directive_when_pr_converge_state_present_in_job_dir(tmp_path: Path) -> None:
    state_path = _write_state_file(
        tmp_path / "job",
        "pr-converge-state.json",
        {
            "skill": "pr-converge",
            "phase": "BUGTEAM",
            "current_head": "abc123def456",
            "tick_count": 7,
            "worktree": "/work/pr-converge-144",
            "operator_followups": ["confirm bugbot acknowledged trigger"],
        },
    )

    hook_run = _run_hook(
        _precompact_payload(cwd=str(tmp_path), trigger="auto", custom_instructions=""),
        extra_env={"CLAUDE_JOB_DIR": str(tmp_path / "job")},
    )

    assert hook_run.returncode == 0
    assert "precompact-state-preserver" in hook_run.stdout
    assert "MUST PRESERVE" in hook_run.stdout
    assert "CAN DROP" in hook_run.stdout
    assert "RESUMPTION HINT" in hook_run.stdout
    assert state_path.as_posix() in hook_run.stdout
    assert "skill: pr-converge" in hook_run.stdout
    assert "phase: BUGTEAM" in hook_run.stdout
    assert "current_head: abc123def456" in hook_run.stdout
    assert "tick_count: 7" in hook_run.stdout
    assert "worktree: /work/pr-converge-144" in hook_run.stdout
    assert "confirm bugbot acknowledged trigger" in hook_run.stdout
    assert "Per-finding bodies" in hook_run.stdout


def test_no_output_when_no_state_file_anywhere(tmp_path: Path) -> None:
    hook_run = _run_hook(
        _precompact_payload(cwd=str(tmp_path), trigger="auto", custom_instructions=""),
        extra_env={"CLAUDE_JOB_DIR": str(tmp_path / "empty-job")},
    )

    assert hook_run.returncode == 0
    assert hook_run.stdout == ""


def test_manual_trigger_echoes_operator_custom_instructions_before_directive(
    tmp_path: Path,
) -> None:
    _write_state_file(
        tmp_path / "job",
        "pr-converge-state.json",
        {"skill": "pr-converge", "current_head": "deadbeef", "phase": "BUGBOT", "tick_count": 1},
    )
    operator_text = "Preserve the deployment approval thread above all else."

    hook_run = _run_hook(
        _precompact_payload(cwd=str(tmp_path), trigger="manual", custom_instructions=operator_text),
        extra_env={"CLAUDE_JOB_DIR": str(tmp_path / "job")},
    )

    assert hook_run.returncode == 0
    operator_index = hook_run.stdout.find(operator_text)
    directive_index = hook_run.stdout.find("precompact-state-preserver")
    assert operator_index >= 0
    assert directive_index > operator_index


def test_malformed_stdin_exits_clean_with_no_output(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not json at all",
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "CLAUDE_JOB_DIR": str(tmp_path)},
    )

    assert completed.returncode == 0
    assert completed.stdout == ""


def test_project_local_state_directory_is_scanned_when_job_dir_unset(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_path = _write_state_file(
        project_root / ".claude" / "state",
        "loop-state.json",
        {"skill": "loop", "phase": "polling", "current_head": "feedfacecafe", "tick_count": 3},
    )
    sterile_env = {
        each_key: each_value
        for each_key, each_value in os.environ.items()
        if each_key != "CLAUDE_JOB_DIR"
    }

    hook_run = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(_precompact_payload(cwd=str(project_root), trigger="auto", custom_instructions="")),
        text=True,
        capture_output=True,
        check=False,
        env=sterile_env,
    )

    assert hook_run.returncode == 0
    assert state_path.as_posix() in hook_run.stdout
    assert "skill: loop" in hook_run.stdout


def test_state_file_above_size_cap_is_skipped(tmp_path: Path) -> None:
    bloated_body = {"skill": "pr-converge", "noise": "x" * 400_000}
    _write_state_file(tmp_path / "job", "pr-converge-state.json", bloated_body)

    hook_run = _run_hook(
        _precompact_payload(cwd=str(tmp_path), trigger="auto", custom_instructions=""),
        extra_env={"CLAUDE_JOB_DIR": str(tmp_path / "job")},
    )

    assert hook_run.returncode == 0
    assert hook_run.stdout == ""


def test_wrong_hook_event_name_produces_no_output(tmp_path: Path) -> None:
    _write_state_file(
        tmp_path / "job", "pr-converge-state.json", {"skill": "pr-converge", "current_head": "x"}
    )
    foreign_payload = _precompact_payload(cwd=str(tmp_path), trigger="auto", custom_instructions="")
    foreign_payload["hook_event_name"] = "PostToolUse"

    hook_run = _run_hook(foreign_payload, extra_env={"CLAUDE_JOB_DIR": str(tmp_path / "job")})

    assert hook_run.returncode == 0
    assert hook_run.stdout == ""
