"""Tests for git_hooks_self_heal — SessionStart hook for git-hook install resilience."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

_SESSION_DIRECTORY = Path(__file__).resolve().parent
_HOOKS_ROOT_DIRECTORY = _SESSION_DIRECTORY.parent
for each_sys_path_candidate in (str(_SESSION_DIRECTORY), str(_HOOKS_ROOT_DIRECTORY)):
    if each_sys_path_candidate not in sys.path:
        sys.path.insert(0, each_sys_path_candidate)

import git_hooks_self_heal as self_heal
from config.git_hooks_self_heal_constants import (
    ALL_EXPECTED_HOOKS_PATH_SEGMENTS_FROM_HOME,
    ALL_KNOWN_GIT_HOOK_FILENAMES,
)


def _build_expected_hooks_directory(home_directory: Path) -> Path:
    return home_directory.joinpath(*ALL_EXPECTED_HOOKS_PATH_SEGMENTS_FROM_HOME)


def _populate_shims(hooks_directory: Path) -> None:
    hooks_directory.mkdir(parents=True, exist_ok=True)
    for each_filename in ALL_KNOWN_GIT_HOOK_FILENAMES:
        (hooks_directory / each_filename).write_text("#!/usr/bin/env python3\n")


class StubInstallerInvocation:
    def __init__(self, exit_code: int = 0, stderr_message: str = "") -> None:
        self.exit_code = exit_code
        self.stderr_message = stderr_message
        self.was_called = False

    def __call__(self, *_call_arguments, **_call_keyword_arguments) -> int:
        self.was_called = True
        return self.exit_code


def _run_self_heal(
    home_directory: Path,
    git_hooks_path_value: str,
    installer_invocation: StubInstallerInvocation,
) -> tuple[str, str, int]:
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    exit_code = 0
    try:
        with (
            patch.object(self_heal, "user_home_directory", return_value=home_directory),
            patch.object(
                self_heal,
                "read_global_hooks_path",
                return_value=git_hooks_path_value,
            ),
            patch.object(self_heal, "invoke_installer", installer_invocation),
            patch("sys.stdout", captured_stdout),
            patch("sys.stderr", captured_stderr),
        ):
            self_heal.main()
    except SystemExit as raised_system_exit:
        exit_code = raised_system_exit.code or 0
    return captured_stdout.getvalue(), captured_stderr.getvalue(), exit_code


class TestHappyPath:
    def test_already_installed_exits_silently_without_invoking_installer(
        self, tmp_path: Path
    ) -> None:
        expected_hooks_directory = _build_expected_hooks_directory(tmp_path)
        _populate_shims(expected_hooks_directory)
        installer_invocation = StubInstallerInvocation()

        captured_stdout, captured_stderr, exit_code = _run_self_heal(
            home_directory=tmp_path,
            git_hooks_path_value=str(expected_hooks_directory),
            installer_invocation=installer_invocation,
        )

        assert exit_code == 0
        assert captured_stdout == ""
        assert captured_stderr == ""
        assert installer_invocation.was_called is False


class TestMissingShim:
    def test_missing_shim_invokes_installer(self, tmp_path: Path) -> None:
        expected_hooks_directory = _build_expected_hooks_directory(tmp_path)
        expected_hooks_directory.mkdir(parents=True)
        installer_invocation = StubInstallerInvocation(exit_code=0)

        _, captured_stderr, exit_code = _run_self_heal(
            home_directory=tmp_path,
            git_hooks_path_value=str(expected_hooks_directory),
            installer_invocation=installer_invocation,
        )

        assert exit_code == 0
        assert installer_invocation.was_called is True
        assert captured_stderr == ""


class TestUnsetCoreHooksPath:
    def test_empty_core_hooks_path_invokes_installer(self, tmp_path: Path) -> None:
        installer_invocation = StubInstallerInvocation(exit_code=0)

        _, _, exit_code = _run_self_heal(
            home_directory=tmp_path,
            git_hooks_path_value="",
            installer_invocation=installer_invocation,
        )

        assert exit_code == 0
        assert installer_invocation.was_called is True


class TestInstallerFailure:
    def test_installer_failure_prints_stderr_and_exits_zero(
        self, tmp_path: Path
    ) -> None:
        installer_invocation = StubInstallerInvocation(exit_code=1)

        _, captured_stderr, exit_code = _run_self_heal(
            home_directory=tmp_path,
            git_hooks_path_value="",
            installer_invocation=installer_invocation,
        )

        assert exit_code == 0
        assert installer_invocation.was_called is True
        assert "claude-dev-env" in captured_stderr


class TestRespectsExternalHookManager:
    def test_husky_hooks_path_does_not_invoke_installer(self, tmp_path: Path) -> None:
        installer_invocation = StubInstallerInvocation()

        _, captured_stderr, exit_code = _run_self_heal(
            home_directory=tmp_path,
            git_hooks_path_value=str(tmp_path / "node_modules" / "husky"),
            installer_invocation=installer_invocation,
        )

        assert exit_code == 0
        assert installer_invocation.was_called is False
        assert captured_stderr == ""


class TestReadGlobalHooksPathIntegration:
    def test_read_global_hooks_path_returns_string(self) -> None:
        observed_value = self_heal.read_global_hooks_path()
        assert isinstance(observed_value, str)


class TestExpectedHooksDirectoryHelper:
    def test_expected_hooks_directory_uses_constants(self, tmp_path: Path) -> None:
        observed_directory = self_heal.expected_hooks_directory(tmp_path)
        expected_directory = _build_expected_hooks_directory(tmp_path)
        assert observed_directory == expected_directory
