"""Tests for bugteam_preflight git hooks path verification.

Covers:
- core.hooksPath unset: exits non-zero with correction message
- core.hooksPath pointing to the correct claude hooks dir: exits zero
- core.hooksPath pointing elsewhere (husky override): exits non-zero
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch


def _load_preflight_module() -> ModuleType:
    module_path = Path(__file__).parent / "bugteam_preflight.py"
    spec = importlib.util.spec_from_file_location("bugteam_preflight", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bugteam_preflight = _load_preflight_module()


def _make_completed_process(
    stdout: str, returncode: int
) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = returncode
    return process


def test_should_exit_nonzero_when_core_hooks_path_unset(capsys) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        exit_code = bugteam_preflight.verify_git_hooks_path()
    assert exit_code != 0
    captured = capsys.readouterr()
    assert "core.hooksPath" in captured.err
    assert "npx claude-dev-env" in captured.err or "git config" in captured.err


def test_should_exit_zero_when_core_hooks_path_points_to_claude_hooks(tmp_path) -> None:
    claude_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    claude_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(claude_hooks_path) + "\n", returncode=0
        )
        exit_code = bugteam_preflight.verify_git_hooks_path()
    assert exit_code == 0


def test_should_exit_nonzero_when_core_hooks_path_points_elsewhere(capsys) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "/some/other/path/.husky\n", returncode=0
        )
        exit_code = bugteam_preflight.verify_git_hooks_path()
    assert exit_code != 0
    captured = capsys.readouterr()
    assert "core.hooksPath" in captured.err


def test_should_include_correction_commands_in_error_message(capsys) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        bugteam_preflight.verify_git_hooks_path()
    captured = capsys.readouterr()
    assert (
        "npx claude-dev-env" in captured.err
        or "git config --global core.hooksPath" in captured.err
    )


def test_main_should_exit_nonzero_when_hooks_path_unset() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        exit_code = bugteam_preflight.main(["--no-pytest"])
    assert exit_code != 0


def test_main_should_continue_when_hooks_path_valid(tmp_path) -> None:
    claude_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    claude_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(claude_hooks_path) + "\n", returncode=0
        )
        exit_code = bugteam_preflight.main(["--no-pytest"])
    assert exit_code == 0
