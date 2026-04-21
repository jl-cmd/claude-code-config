"""Tests for bugteam_preflight.verify_git_hooks_path edge cases flagged on PR #231.

A hooksPath value with a trailing slash (e.g. ~/.claude/hooks/git-hooks/) was
incorrectly failing the suffix check because endswith("hooks/git-hooks") does
not match a trailing "/".
"""

from __future__ import annotations

import importlib.util
import subprocess
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


def test_should_accept_hooks_path_with_trailing_slash() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "/home/user/.claude/hooks/git-hooks/\n", returncode=0
        )
        exit_code = bugteam_preflight.verify_git_hooks_path()
    assert exit_code == 0, (
        "hooksPath with trailing slash must pass verification after normalization"
    )


def test_should_accept_hooks_path_with_backslash_and_trailing_slash() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "C:\\Users\\user\\.claude\\hooks\\git-hooks\\\n", returncode=0
        )
        exit_code = bugteam_preflight.verify_git_hooks_path()
    assert exit_code == 0, (
        "Windows hooksPath with trailing backslash must pass after normalization"
    )
