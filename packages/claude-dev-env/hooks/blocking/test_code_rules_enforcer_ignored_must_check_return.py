"""Tests for check_ignored_must_check_return — discarded must-check outcomes.

A bare-statement call to a function in MUST_CHECK_RETURN_FUNCTION_NAMES
discards the only failure signal it produces. An assigned or branched-on
call is exempt; only bare ``ast.Expr`` calls are flagged.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def check_ignored_must_check_return(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_ignored_must_check_return(content, file_path)


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/clicker.py"
TEST_FILE_PATH = "/project/src/test_clicker.py"


def test_should_flag_bare_find_and_click_call() -> None:
    source = "def step() -> None:\n    find_and_click('#submit')\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert any("find_and_click" in each for each in issues), (
        f"Expected discarded-return flag for find_and_click, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_flag_bare_write_outcome_call() -> None:
    source = "def step() -> None:\n    write_outcome('done')\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert any("write_outcome" in each for each in issues), (
        f"Expected discarded-return flag for write_outcome, got: {issues!r}"
    )
    assert len(issues) == 1


def test_should_flag_attribute_call_with_must_check_name() -> None:
    source = "def step() -> None:\n    self.find_and_click('#submit')\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert len(issues) == 1, f"Attribute call terminal name must be resolved, got: {issues!r}"


def test_should_not_flag_assigned_find_and_click() -> None:
    source = "def step() -> None:\n    clicked = find_and_click('#submit')\n    print(clicked)\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Assigned call must not be flagged, got: {issues!r}"


def test_should_not_flag_branched_find_and_click() -> None:
    source = "def step() -> None:\n    if find_and_click('#submit'):\n        pass\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Branched-on call must not be flagged, got: {issues!r}"


def test_should_not_flag_unrelated_bare_call() -> None:
    source = "def step() -> None:\n    print('hello')\n"
    issues = check_ignored_must_check_return(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Unrelated call must not be flagged, got: {issues!r}"


def test_should_skip_test_file() -> None:
    source = "def step() -> None:\n    find_and_click('#submit')\n"
    issues = check_ignored_must_check_return(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_ignored_must_check_return("def step(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_discarded_return() -> None:
    source = "def step() -> None:\n    find_and_click('#submit')\n"
    issues = validate_content(source, PRODUCTION_FILE_PATH, old_content="")
    matching_issues = [each for each in issues if "find_and_click" in each]
    assert matching_issues, (
        f"Expected validate_content to surface the discarded-return issue, got: {issues!r}"
    )
