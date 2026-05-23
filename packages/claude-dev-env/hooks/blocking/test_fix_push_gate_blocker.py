"""Behavior tests for the fix_push_gate_blocker PreToolUse hook.

Detection, loop-scoping, and gate-result-file writing run against real data
(real regex, real temp git repos, real filesystem). The exit-1 deny path's
end-to-end correctness reduces to ``code_rules_gate.py`` exiting 1 (covered by
its own suite) plus main's blocking branch; full main-deny coverage would
require either mocks (excluded by the zero-mock test philosophy) or a live
GitHub PR for ``gh pr view``, so it is verified by a real run during PR-1
acceptance rather than here.
"""

import importlib.util
import io
import json
import pathlib
import subprocess
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "fix_push_gate_blocker",
    _HOOK_DIR / "fix_push_gate_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

_is_gated_action = hook_module._is_gated_action
_loop_is_active = hook_module._loop_is_active
_write_gate_result = hook_module._write_gate_result
_PUSH_PATTERN = hook_module.GIT_PUSH_COMMAND_PATTERN
_GATED_MCP_WRITE_TOOLS = hook_module.ALL_GATED_MCP_WRITE_TOOLS
_BASH_TOOL_NAME = hook_module.BASH_TOOL_NAME
_GATE_RESULT_FILENAME_TEMPLATE = hook_module.GATE_RESULT_FILENAME_TEMPLATE
_LOOP_STATE_FILENAME = hook_module.LOOP_STATE_FILENAME
_run_gate = hook_module._run_gate

_IN_REPO_GATE_SCRIPT = (
    _HOOK_DIR.parent.parent / "_shared" / "pr-loop" / "scripts" / "code_rules_gate.py"
)


def _git(repo_root: pathlib.Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *arguments],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )


def _init_git_repo(repo_root: pathlib.Path) -> None:
    subprocess.run(["git", "init"], cwd=str(repo_root), check=True, capture_output=True)
    subprocess.run(
        ["git", "checkout", "-b", "convergetest"],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "core.hooksPath", str(repo_root / ".disabledhooks")],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )


def _run_main_with(payload: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()
    return int(exit_info.value.code)


def test_gated_action_detects_bash_git_push() -> None:
    assert _is_gated_action(_BASH_TOOL_NAME, "git push origin HEAD") is True


def test_gated_action_detects_git_dash_c_push() -> None:
    assert _is_gated_action(_BASH_TOOL_NAME, "git -C /tmp/wt push") is True


def test_gated_action_detects_compound_push() -> None:
    assert _is_gated_action(_BASH_TOOL_NAME, "gh pr ready --undo && git push") is True


def test_gated_action_ignores_git_log_mentioning_push() -> None:
    assert _is_gated_action(_BASH_TOOL_NAME, "git log --grep=push") is False


def test_gated_action_ignores_git_pushd_word() -> None:
    assert _is_gated_action(_BASH_TOOL_NAME, "git pushd") is False


def test_gated_action_ignores_non_git_bash() -> None:
    assert _is_gated_action(_BASH_TOOL_NAME, "ls -la") is False


def test_gated_action_detects_every_listed_mcp_write_tool() -> None:
    assert _GATED_MCP_WRITE_TOOLS
    for each_tool in _GATED_MCP_WRITE_TOOLS:
        assert _is_gated_action(each_tool, "") is True


def test_gated_action_ignores_unlisted_mcp_tool() -> None:
    assert _is_gated_action("mcp__plugin_github_github__add_issue_comment", "") is False


def test_push_pattern_matches_force_with_lease() -> None:
    assert _PUSH_PATTERN.search("git push --force-with-lease origin HEAD")


def test_loop_is_active_with_state_file(tmp_path: pathlib.Path) -> None:
    (tmp_path / _LOOP_STATE_FILENAME).write_text("{}", encoding="utf-8")
    assert _loop_is_active(tmp_path) is True


def test_loop_is_active_with_outcomes_file(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".bugteam-pr5-loop2.outcomes.xml").write_text("<outcomes/>", encoding="utf-8")
    assert _loop_is_active(tmp_path) is True


def test_loop_is_inactive_when_no_evidence(tmp_path: pathlib.Path) -> None:
    assert _loop_is_active(tmp_path) is False


def test_write_gate_result_records_passing_verdict(tmp_path: pathlib.Path) -> None:
    _write_gate_result(tmp_path, 484, True, "abc123", "worktree-base")
    written = tmp_path / _GATE_RESULT_FILENAME_TEMPLATE.format(number=484)
    assert written.is_file()
    recorded = json.loads(written.read_text(encoding="utf-8"))
    assert recorded["passed"] is True
    assert recorded["head_sha"] == "abc123"
    assert recorded["base_ref"] == "worktree-base"
    assert recorded["checked_at"]


def test_write_gate_result_records_failing_verdict(tmp_path: pathlib.Path) -> None:
    _write_gate_result(tmp_path, 99, False, "def456", "main")
    written = tmp_path / _GATE_RESULT_FILENAME_TEMPLATE.format(number=99)
    recorded = json.loads(written.read_text(encoding="utf-8"))
    assert recorded["passed"] is False


def test_main_allows_non_git_bash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    assert _run_main_with(payload, monkeypatch) == 0
    assert capsys.readouterr().out.strip() == ""


def test_main_allows_push_outside_managed_loop(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _init_git_repo(tmp_path)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git push", "cwd": str(tmp_path)},
    }
    assert _run_main_with(payload, monkeypatch) == 0
    assert capsys.readouterr().out.strip() == ""


def _seed_base_commit(repo_root: pathlib.Path, sample_body: str) -> None:
    (repo_root / "sample.py").write_text(sample_body, encoding="utf-8")
    _git(repo_root, "add", "sample.py")
    _git(repo_root, "commit", "-m", "base")
    _git(repo_root, "update-ref", "refs/remotes/origin/base", "HEAD")


def test_run_gate_blocks_planted_violation(tmp_path: pathlib.Path) -> None:
    _init_git_repo(tmp_path)
    _seed_base_commit(tmp_path, "def first() -> int:\n    return 0\n")
    (tmp_path / "sample.py").write_text(
        "def first() -> int:\n    return 0\n\n\ndef second() -> int:\n    cfg = 5\n    return cfg\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", "sample.py")
    _git(tmp_path, "commit", "-m", "violation")
    return_code, gate_output = _run_gate(_IN_REPO_GATE_SCRIPT, tmp_path, "base")
    assert return_code == 1, gate_output
    assert "sample.py" in gate_output


def test_run_gate_allows_clean_change(tmp_path: pathlib.Path) -> None:
    _init_git_repo(tmp_path)
    _seed_base_commit(tmp_path, "def first() -> int:\n    return 0\n")
    (tmp_path / "sample.py").write_text(
        "def first() -> int:\n    return 0\n\n\ndef second() -> int:\n    return 1\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", "sample.py")
    _git(tmp_path, "commit", "-m", "clean")
    return_code, gate_output = _run_gate(_IN_REPO_GATE_SCRIPT, tmp_path, "base")
    assert return_code == 0, gate_output
