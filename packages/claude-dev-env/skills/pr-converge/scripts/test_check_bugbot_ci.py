"""Tests for check_bugbot_ci silent-pass detection.

Covers:
- is_bugbot_run_clean returns True for completed success / completed neutral
- is_bugbot_run_clean returns False for completed failure, in_progress, missing
- is_bugbot_run_clean returns None when the gh CLI fails
- main(--check-clean) returns 0 on clean, 1 on not-clean, and
  EXIT_CODE_GH_ERROR on gh CLI failure (with stderr diagnostics)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def check_bugbot_ci_module() -> ModuleType:
    """Load check_bugbot_ci as an isolated module without polluting sys.path.

    The production script performs its own membership-guarded
    sys.path.insert during exec_module so its config dependency
    resolves. Any previously cached ``config`` package from a sibling
    test is evicted from sys.modules so the production script's
    sys.path.insert can take effect for its own config package. The
    eviction is scoped to this fixture: cached entries are restored
    after exec_module returns so sibling tests are unaffected.
    """
    module_path = _SCRIPTS_DIRECTORY / "check_bugbot_ci.py"
    spec = importlib.util.spec_from_file_location("check_bugbot_ci", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    evicted_config_modules = {
        each_module_name: sys.modules.pop(each_module_name)
        for each_module_name in list(sys.modules)
        if each_module_name == "config" or each_module_name.startswith("config.")
    }
    try:
        spec.loader.exec_module(module)
    finally:
        for each_module_name, each_module_value in evicted_config_modules.items():
            sys.modules.setdefault(each_module_name, each_module_value)
    return module


def _make_completed_process(
    stdout: str, returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.stderr = ""
    process.returncode = returncode
    return process


def _build_stdout(*all_check_entries: dict[str, object]) -> str:
    return "\n".join(json.dumps(each_entry) for each_entry in all_check_entries) + "\n"


def test_should_return_true_when_bugbot_completed_with_success_conclusion(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "success"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is True


def test_should_return_true_when_bugbot_completed_with_neutral_conclusion(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "bugbot", "status": "completed", "conclusion": "neutral"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is True


def test_should_return_false_when_bugbot_completed_with_failure_conclusion(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "failure"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is False


def test_should_return_false_when_bugbot_still_in_progress(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "in_progress", "conclusion": None}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is False


def test_should_return_false_when_no_bugbot_check_run_present(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "ci-other", "status": "completed", "conclusion": "success"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is False


def test_should_return_none_when_gh_cli_fails(
    check_bugbot_ci_module: ModuleType,
) -> None:
    failing_process = MagicMock(spec=subprocess.CompletedProcess)
    failing_process.stdout = ""
    failing_process.stderr = "boom"
    failing_process.returncode = 1
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=failing_process,
    ):
        is_clean = check_bugbot_ci_module.is_bugbot_run_clean(
            owner="acme", repo="repo", sha="abc"
        )
    assert is_clean is None


def test_main_check_clean_should_return_gh_error_code_when_gh_cli_fails(
    check_bugbot_ci_module: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failing_process = MagicMock(spec=subprocess.CompletedProcess)
    failing_process.stdout = ""
    failing_process.stderr = "boom"
    failing_process.returncode = 1
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=failing_process,
    ):
        exit_code = check_bugbot_ci_module.main(
            ["--check-clean", "--owner", "acme", "--repo", "repo", "--sha", "abc"]
        )
    assert exit_code == check_bugbot_ci_module.EXIT_CODE_GH_ERROR
    captured = capsys.readouterr()
    assert "gh api error: boom" in captured.err


def test_main_check_clean_should_return_zero_when_bugbot_clean(
    check_bugbot_ci_module: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "success"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        exit_code = check_bugbot_ci_module.main(
            ["--check-clean", "--owner", "acme", "--repo", "repo", "--sha", "abc"]
        )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "not clean" not in captured.out


def test_main_check_clean_should_return_one_when_bugbot_not_clean(
    check_bugbot_ci_module: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "completed", "conclusion": "failure"}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        exit_code = check_bugbot_ci_module.main(
            ["--check-clean", "--owner", "acme", "--repo", "repo", "--sha", "abc"]
        )
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not clean" in captured.out


def test_main_check_active_should_return_zero_when_bugbot_in_progress(
    check_bugbot_ci_module: ModuleType,
) -> None:
    stdout = _build_stdout(
        {"name": "Cursor Bugbot", "status": "in_progress", "conclusion": None}
    )
    with patch.object(
        check_bugbot_ci_module,
        "_run_check_runs_api",
        return_value=_make_completed_process(stdout),
    ):
        exit_code = check_bugbot_ci_module.main(
            ["--check-active", "--owner", "acme", "--repo", "repo", "--sha", "abc"]
        )
    assert exit_code == 0


def test_main_should_reject_check_clean_and_check_active_together(
    check_bugbot_ci_module: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        check_bugbot_ci_module.main(
            [
                "--check-clean",
                "--check-active",
                "--owner",
                "acme",
                "--repo",
                "repo",
                "--sha",
                "abc",
            ]
        )
    captured = capsys.readouterr()
    assert "not allowed with" in captured.err or "mutually exclusive" in captured.err
