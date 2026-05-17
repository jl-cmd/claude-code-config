"""Unit tests for gh-pr-author-enforcer PreToolUse hook (auto-switch behavior)."""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys
from typing import Iterator
from unittest import mock

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_module_spec = importlib.util.spec_from_file_location(
    "gh_pr_author_enforcer",
    _HOOK_DIR / "gh_pr_author_enforcer.py",
)
assert hook_module_spec is not None
assert hook_module_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_module_spec)
hook_module_spec.loader.exec_module(hook_module)


def _make_stdin_payload(command: str, session_id: str = "test-session-001") -> str:
    return json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "session_id": session_id,
        }
    )


@pytest.fixture
def required_account_jonecho(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("GITHUB_DEFAULT_ACCOUNT", "JonEcho")
    yield "JonEcho"


@pytest.fixture
def isolated_state_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> Iterator[pathlib.Path]:
    monkeypatch.setattr(hook_module.tempfile, "gettempdir", lambda: str(tmp_path))
    yield tmp_path


def _run_hook_with(
    stdin_text: str,
    active_account_or_none: str | None,
    monkeypatch: pytest.MonkeyPatch,
    switch_succeeds: bool,
) -> tuple[int, str, list[str]]:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    monkeypatch.setattr(hook_module, "_active_gh_account", lambda: active_account_or_none)
    switch_invocations: list[str] = []

    def _fake_switch(to_account: str) -> bool:
        switch_invocations.append(to_account)
        return switch_succeeds

    monkeypatch.setattr(hook_module, "_switch_gh_account", _fake_switch)
    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()
    exit_code = exit_info.value.code if isinstance(exit_info.value.code, int) else 0
    return exit_code, captured_stdout.getvalue(), switch_invocations


def test_command_invokes_gh_pr_create_matches_basic_form() -> None:
    assert hook_module._command_invokes_gh_pr_create("gh pr create --title T")


def test_command_invokes_gh_pr_create_matches_chained_form() -> None:
    assert hook_module._command_invokes_gh_pr_create("git push && gh pr create")


def test_command_invokes_gh_pr_create_rejects_pr_edit() -> None:
    assert not hook_module._command_invokes_gh_pr_create("gh pr edit 10 --title X")


def test_command_invokes_gh_pr_create_rejects_substring() -> None:
    assert not hook_module._command_invokes_gh_pr_create("some-gh pr created-by")


def test_command_uses_web_flag_matches_long_form() -> None:
    assert hook_module._command_uses_web_flag("gh pr create --web")


def test_command_uses_web_flag_matches_short_form() -> None:
    assert hook_module._command_uses_web_flag("gh pr create -w")


def test_command_uses_web_flag_rejects_webhook_substring() -> None:
    assert not hook_module._command_uses_web_flag("gh pr create --webhook=foo")


def test_main_auto_switches_when_active_account_mismatches(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == ["JonEcho"]
    state_file = hook_module._state_file_path("test-session-001")
    assert state_file.exists()
    persisted_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert persisted_state == {
        "original_account": "jl-cmd",
        "primary_account": "JonEcho",
    }


def test_main_denies_when_auto_switch_fails(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=False,
    )
    assert exit_code == 0
    assert switch_invocations == ["JonEcho"]
    payload = json.loads(stdout_text)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    deny_reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert "JonEcho" in deny_reason
    assert "jl-cmd" in deny_reason
    assert "gh auth switch --user JonEcho" in deny_reason
    state_file = hook_module._state_file_path("test-session-001")
    assert not state_file.exists()


def test_main_no_op_when_active_account_matches(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="JonEcho",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    state_file = hook_module._state_file_path("test-session-001")
    assert not state_file.exists()


def test_main_allows_when_required_account_unset(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    monkeypatch.delenv("GITHUB_DEFAULT_ACCOUNT", raising=False)
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_web_flow_even_when_mismatched(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --web --title T"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_short_web_flag_even_when_mismatched(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create -w --title T"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_non_bash_tool(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    stdin_text = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "x", "content": "y"},
            "session_id": "test-session-001",
        }
    )
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        stdin_text,
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_unrelated_bash_command(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("git status"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_gh_pr_edit(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr edit 10 --title X"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_when_active_account_undetermined(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T"),
        active_account_or_none=None,
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_invalid_stdin_json(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        "not-json",
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_state_file_path_uses_session_id(
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("abc-123")
    assert state_file.parent == isolated_state_directory
    assert state_file.name == "gh_pr_author_swap_abc-123.json"


def test_state_file_path_falls_back_to_default_when_session_id_empty(
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("")
    assert state_file.name == "gh_pr_author_swap_default.json"


def test_active_gh_account_returns_login_on_success() -> None:
    completed = mock.Mock(returncode=0, stdout="JonEcho\n")
    with mock.patch.object(hook_module.subprocess, "run", return_value=completed):
        assert hook_module._active_gh_account() == "JonEcho"


def test_active_gh_account_returns_none_on_nonzero_exit() -> None:
    completed = mock.Mock(returncode=1, stdout="")
    with mock.patch.object(hook_module.subprocess, "run", return_value=completed):
        assert hook_module._active_gh_account() is None


def test_active_gh_account_returns_none_when_gh_missing() -> None:
    with mock.patch.object(hook_module.subprocess, "run", side_effect=FileNotFoundError):
        assert hook_module._active_gh_account() is None


def test_active_gh_account_returns_none_on_timeout() -> None:
    with mock.patch.object(
        hook_module.subprocess,
        "run",
        side_effect=hook_module.subprocess.TimeoutExpired(cmd="gh", timeout=5),
    ):
        assert hook_module._active_gh_account() is None


def test_switch_gh_account_returns_true_on_success() -> None:
    completed = mock.Mock(returncode=0, stdout="", stderr="")
    with mock.patch.object(hook_module.subprocess, "run", return_value=completed):
        assert hook_module._switch_gh_account("JonEcho") is True


def test_switch_gh_account_returns_false_on_nonzero_exit() -> None:
    completed = mock.Mock(returncode=1, stdout="", stderr="auth failed")
    with mock.patch.object(hook_module.subprocess, "run", return_value=completed):
        assert hook_module._switch_gh_account("JonEcho") is False


def test_switch_gh_account_returns_false_when_gh_missing() -> None:
    with mock.patch.object(hook_module.subprocess, "run", side_effect=FileNotFoundError):
        assert hook_module._switch_gh_account("JonEcho") is False


def test_switch_gh_account_returns_false_on_timeout() -> None:
    with mock.patch.object(
        hook_module.subprocess,
        "run",
        side_effect=hook_module.subprocess.TimeoutExpired(cmd="gh", timeout=10),
    ):
        assert hook_module._switch_gh_account("JonEcho") is False
