"""Unit tests for gh-pr-author-session-cleanup SessionStart hook."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from typing import Iterator
from unittest import mock

import pytest

_SESSION_DIR = pathlib.Path(__file__).resolve().parent
_HOOKS_ROOT = _SESSION_DIR.parent
for each_sys_path_entry in (str(_SESSION_DIR), str(_HOOKS_ROOT)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

hook_module_spec = importlib.util.spec_from_file_location(
    "gh_pr_author_session_cleanup",
    _SESSION_DIR / "gh_pr_author_session_cleanup.py",
)
assert hook_module_spec is not None
assert hook_module_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_module_spec)
hook_module_spec.loader.exec_module(hook_module)


def _write_state_file(state_file: pathlib.Path, original_account: str) -> None:
    state_file.write_text(
        json.dumps(
            {
                "original_account": original_account,
                "primary_account": "JonEcho",
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def required_account_jonecho(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("GITHUB_DEFAULT_ACCOUNT", "JonEcho")
    yield "JonEcho"


@pytest.fixture
def isolated_temp_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> Iterator[pathlib.Path]:
    monkeypatch.setattr(hook_module.tempfile, "gettempdir", lambda: str(tmp_path))
    yield tmp_path


def _install_fake_switch(monkeypatch: pytest.MonkeyPatch, switch_succeeds: bool) -> list[str]:
    switch_invocations: list[str] = []

    def _fake_switch(to_account: str) -> bool:
        switch_invocations.append(to_account)
        return switch_succeeds

    monkeypatch.setattr(hook_module, "_switch_gh_account", _fake_switch)
    return switch_invocations


def test_main_no_op_when_no_state_files_present(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_temp_directory: pathlib.Path,
) -> None:
    switch_invocations = _install_fake_switch(monkeypatch, switch_succeeds=True)
    hook_module.main()
    assert switch_invocations == []


def test_main_restores_one_stale_state_file(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_temp_directory: pathlib.Path,
) -> None:
    state_file = isolated_temp_directory / "gh_pr_author_swap_session-A.json"
    _write_state_file(state_file, original_account="jl-cmd")
    switch_invocations = _install_fake_switch(monkeypatch, switch_succeeds=True)

    hook_module.main()

    assert switch_invocations == ["jl-cmd"]
    assert not state_file.exists()


def test_main_restores_multiple_stale_state_files(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_temp_directory: pathlib.Path,
) -> None:
    state_file_a = isolated_temp_directory / "gh_pr_author_swap_session-A.json"
    state_file_b = isolated_temp_directory / "gh_pr_author_swap_session-B.json"
    state_file_c = isolated_temp_directory / "gh_pr_author_swap_session-C.json"
    _write_state_file(state_file_a, original_account="jl-cmd")
    _write_state_file(state_file_b, original_account="other-user")
    _write_state_file(state_file_c, original_account="third-user")
    switch_invocations = _install_fake_switch(monkeypatch, switch_succeeds=True)

    hook_module.main()

    assert sorted(switch_invocations) == ["jl-cmd", "other-user", "third-user"]
    assert not state_file_a.exists()
    assert not state_file_b.exists()
    assert not state_file_c.exists()


def test_main_deletes_malformed_state_file_without_switching(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_temp_directory: pathlib.Path,
) -> None:
    malformed_state_file = isolated_temp_directory / "gh_pr_author_swap_broken.json"
    malformed_state_file.write_text("{not valid json", encoding="utf-8")
    switch_invocations = _install_fake_switch(monkeypatch, switch_succeeds=True)

    hook_module.main()

    assert switch_invocations == []
    assert not malformed_state_file.exists()


def test_main_no_op_when_required_account_unset(
    monkeypatch: pytest.MonkeyPatch,
    isolated_temp_directory: pathlib.Path,
) -> None:
    monkeypatch.delenv("GITHUB_DEFAULT_ACCOUNT", raising=False)
    state_file = isolated_temp_directory / "gh_pr_author_swap_session-A.json"
    _write_state_file(state_file, original_account="jl-cmd")
    switch_invocations = _install_fake_switch(monkeypatch, switch_succeeds=True)

    hook_module.main()

    assert switch_invocations == []
    assert state_file.exists()


def test_main_preserves_state_file_when_switch_fails(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_temp_directory: pathlib.Path,
) -> None:
    state_file = isolated_temp_directory / "gh_pr_author_swap_session-A.json"
    _write_state_file(state_file, original_account="jl-cmd")
    switch_invocations = _install_fake_switch(monkeypatch, switch_succeeds=False)

    hook_module.main()

    assert switch_invocations == ["jl-cmd"]
    assert state_file.exists()


def test_main_no_op_when_required_account_blank(
    monkeypatch: pytest.MonkeyPatch,
    isolated_temp_directory: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_DEFAULT_ACCOUNT", "   ")
    state_file = isolated_temp_directory / "gh_pr_author_swap_session-A.json"
    _write_state_file(state_file, original_account="jl-cmd")
    switch_invocations = _install_fake_switch(monkeypatch, switch_succeeds=True)

    hook_module.main()

    assert switch_invocations == []
    assert state_file.exists()


def test_main_ignores_unrelated_temp_files(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_temp_directory: pathlib.Path,
) -> None:
    unrelated_file = isolated_temp_directory / "unrelated-tempfile.txt"
    unrelated_file.write_text("not a swap state file", encoding="utf-8")
    sibling_swap_file = isolated_temp_directory / "gh_pr_author_swap_session-A.json"
    _write_state_file(sibling_swap_file, original_account="jl-cmd")
    switch_invocations = _install_fake_switch(monkeypatch, switch_succeeds=True)

    hook_module.main()

    assert switch_invocations == ["jl-cmd"]
    assert not sibling_swap_file.exists()
    assert unrelated_file.exists()


def test_main_continues_after_per_file_switch_failure(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_temp_directory: pathlib.Path,
) -> None:
    state_file_a = isolated_temp_directory / "gh_pr_author_swap_session-A.json"
    state_file_b = isolated_temp_directory / "gh_pr_author_swap_session-B.json"
    _write_state_file(state_file_a, original_account="failing-user")
    _write_state_file(state_file_b, original_account="succeeding-user")

    switch_invocations: list[str] = []

    def _fake_switch(to_account: str) -> bool:
        switch_invocations.append(to_account)
        return to_account == "succeeding-user"

    monkeypatch.setattr(hook_module, "_switch_gh_account", _fake_switch)

    hook_module.main()

    assert sorted(switch_invocations) == ["failing-user", "succeeding-user"]
    assert state_file_a.exists()
    assert not state_file_b.exists()


def test_read_original_account_returns_none_for_missing_file(
    isolated_temp_directory: pathlib.Path,
) -> None:
    missing_file = isolated_temp_directory / "does_not_exist.json"
    assert hook_module._read_original_account(missing_file) is None


def test_read_original_account_returns_none_for_non_dict_payload(
    isolated_temp_directory: pathlib.Path,
) -> None:
    list_payload_file = isolated_temp_directory / "list_payload.json"
    list_payload_file.write_text(json.dumps(["jl-cmd"]), encoding="utf-8")
    assert hook_module._read_original_account(list_payload_file) is None


def test_read_original_account_returns_none_for_non_string_value(
    isolated_temp_directory: pathlib.Path,
) -> None:
    bad_type_file = isolated_temp_directory / "bad_type.json"
    bad_type_file.write_text(json.dumps({"original_account": 42}), encoding="utf-8")
    assert hook_module._read_original_account(bad_type_file) is None


def test_read_original_account_returns_none_for_blank_value(
    isolated_temp_directory: pathlib.Path,
) -> None:
    blank_value_file = isolated_temp_directory / "blank.json"
    blank_value_file.write_text(json.dumps({"original_account": "   "}), encoding="utf-8")
    assert hook_module._read_original_account(blank_value_file) is None


def test_switch_gh_account_returns_true_on_success() -> None:
    completed = mock.Mock(returncode=0, stdout="", stderr="")
    with mock.patch.object(hook_module.subprocess, "run", return_value=completed):
        assert hook_module._switch_gh_account("jl-cmd") is True


def test_switch_gh_account_returns_false_on_nonzero_exit() -> None:
    completed = mock.Mock(returncode=1, stdout="", stderr="boom")
    with mock.patch.object(hook_module.subprocess, "run", return_value=completed):
        assert hook_module._switch_gh_account("jl-cmd") is False


def test_switch_gh_account_returns_false_when_gh_missing() -> None:
    with mock.patch.object(hook_module.subprocess, "run", side_effect=FileNotFoundError):
        assert hook_module._switch_gh_account("jl-cmd") is False


def test_switch_gh_account_returns_false_on_timeout() -> None:
    with mock.patch.object(
        hook_module.subprocess,
        "run",
        side_effect=hook_module.subprocess.TimeoutExpired(cmd="gh", timeout=10),
    ):
        assert hook_module._switch_gh_account("jl-cmd") is False


def test_delete_state_file_is_silent_when_already_absent(
    isolated_temp_directory: pathlib.Path,
) -> None:
    missing_file = isolated_temp_directory / "does_not_exist.json"
    hook_module._delete_state_file(missing_file)
    assert not missing_file.exists()


def test_all_stale_state_files_matches_prefix_and_suffix(
    isolated_temp_directory: pathlib.Path,
) -> None:
    matching_a = isolated_temp_directory / "gh_pr_author_swap_session-A.json"
    matching_b = isolated_temp_directory / "gh_pr_author_swap_session-B.json"
    wrong_prefix = isolated_temp_directory / "other_swap_session-C.json"
    wrong_suffix = isolated_temp_directory / "gh_pr_author_swap_session-D.txt"
    for each_file in (matching_a, matching_b, wrong_prefix, wrong_suffix):
        each_file.write_text("{}", encoding="utf-8")

    matched_files = hook_module._all_stale_state_files(isolated_temp_directory)
    matched_names = {each_file.name for each_file in matched_files}

    assert matched_names == {matching_a.name, matching_b.name}
