"""Unit tests for the subprocess_budget_completeness PreToolUse hook."""

import importlib.util
import json
import pathlib
import subprocess
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "subprocess_budget_completeness",
    _HOOK_DIR / "subprocess_budget_completeness.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

find_undercounted_budget = hook_module.find_undercounted_budget

_BUDGET_FLAGS_GIT_TIMEOUT_OMISSION = """
import subprocess

PYTHON_FORMAT_TIMEOUT_SECONDS = 12


def worst_case_python_format_seconds() -> int:
    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    return fix_phase_seconds + format_phase_seconds


def is_untracked_in_git(file_path: str) -> bool:
    git_check = subprocess.run(["git", "ls-files", file_path], timeout=5)
    return git_check.returncode != 0


def run_format(file_path: str) -> None:
    subprocess.run(["ruff", "format", file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)
"""

_BUDGET_COUNTS_EVERY_TIMEOUT = """
import subprocess

PYTHON_FORMAT_TIMEOUT_SECONDS = 12
GIT_CHECK_TIMEOUT_SECONDS = 5


def worst_case_python_format_seconds() -> int:
    git_check_seconds = GIT_CHECK_TIMEOUT_SECONDS
    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS
    return git_check_seconds + fix_phase_seconds + format_phase_seconds


def is_untracked_in_git(file_path: str) -> bool:
    git_check = subprocess.run(["git", "ls-files", file_path], timeout=GIT_CHECK_TIMEOUT_SECONDS)
    return git_check.returncode != 0


def run_format(file_path: str) -> None:
    subprocess.run(["ruff", "format", file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)
"""

_NO_BUDGET_FUNCTION = """
import subprocess


def is_untracked_in_git(file_path: str) -> bool:
    git_check = subprocess.run(["git", "ls-files", file_path], timeout=5)
    return git_check.returncode != 0
"""


def test_flags_budget_helper_that_omits_a_reachable_subprocess_timeout() -> None:
    undercounted_budget = find_undercounted_budget(_BUDGET_FLAGS_GIT_TIMEOUT_OMISSION)
    assert undercounted_budget is not None
    function_name, omitted_literals = undercounted_budget
    assert function_name == "worst_case_python_format_seconds"
    assert omitted_literals == {5}


def test_passes_budget_helper_that_counts_every_subprocess_timeout() -> None:
    assert find_undercounted_budget(_BUDGET_COUNTS_EVERY_TIMEOUT) is None


def test_passes_module_without_a_budget_function() -> None:
    assert find_undercounted_budget(_NO_BUDGET_FUNCTION) is None


def test_passes_module_with_no_subprocess_calls() -> None:
    only_a_budget_function = "def worst_case_seconds() -> int:\n    return 5 + 12\n"
    assert find_undercounted_budget(only_a_budget_function) is None


def _run_hook_on_content(content: str) -> subprocess.CompletedProcess[str]:
    hook_input = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "packages/example/timing_module.py", "content": content},
        }
    )
    return subprocess.run(
        [sys.executable, str(_HOOK_DIR / "subprocess_budget_completeness.py")],
        input=hook_input,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_full_hook_denies_write_with_undercounted_budget() -> None:
    completed_hook = _run_hook_on_content(_BUDGET_FLAGS_GIT_TIMEOUT_OMISSION)
    assert completed_hook.returncode == 0
    hook_output = json.loads(completed_hook.stdout)
    decision = hook_output["hookSpecificOutput"]["permissionDecision"]
    assert decision == "deny"
    assert "5s" in hook_output["hookSpecificOutput"]["permissionDecisionReason"]


def test_full_hook_allows_write_with_complete_budget() -> None:
    completed_hook = _run_hook_on_content(_BUDGET_COUNTS_EVERY_TIMEOUT)
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""
