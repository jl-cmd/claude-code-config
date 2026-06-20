"""Behavior tests for the code_rules_test_assertions code-rules check module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_test_assertions import (  # noqa: E402
    check_constant_equality_tests,
    check_flag_gated_scenario_test_naming,
    check_stale_renamed_symbol_in_test_name,
)

code_rules_enforcer = SimpleNamespace(
    check_constant_equality_tests=check_constant_equality_tests,
    check_flag_gated_scenario_test_naming=check_flag_gated_scenario_test_naming,
    check_stale_renamed_symbol_in_test_name=check_stale_renamed_symbol_in_test_name,
)


CONSTANT_EQUALITY_TEST_FILE_PATH = "packages/app/tests/test_constants.py"
SCENARIO_TEST_FILE_PATH = "packages/app/tests/test_submission_runner_loop.py"
STALE_RENAME_TEST_FILE_PATH = "packages/app/tests/test_scan_priority_queue.py"

_THREE_SIBLINGS_PATCH_THE_FLAG_ONE_SCENARIO_TEST_DOES_NOT = (
    "def test_should_submit_when_gate_passes(monkeypatch) -> None:\n"
    "    assert run() == 'submitted'\n"
    "\n"
    "def test_should_fail_when_reader_raises(monkeypatch) -> None:\n"
    "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
    "    assert run() == 'failed'\n"
    "\n"
    "def test_should_soft_skip_when_mismatch(monkeypatch) -> None:\n"
    "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
    "    assert run() == 'skipped'\n"
    "\n"
    "def test_should_hard_stop_when_unhealthy(monkeypatch) -> None:\n"
    "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
    "    assert run() == 'hard_stop'\n"
)


def test_should_not_flag_two_named_constants_compared_to_each_other() -> None:
    source = (
        "FOO = 'a'\n"
        "BAR = 'b'\n"
        "\n"
        "def test_constants_differ() -> None:\n"
        "    assert FOO == BAR\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(
        source, CONSTANT_EQUALITY_TEST_FILE_PATH
    )
    assert issues == [], (
        f"Expected no flag when both sides are named constants, got: {issues}"
    )


def test_should_flag_named_constant_compared_to_literal() -> None:
    source = (
        "FOO = 'a'\n"
        "\n"
        "def test_foo_value() -> None:\n"
        "    assert FOO == 'literal'\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(
        source, CONSTANT_EQUALITY_TEST_FILE_PATH
    )
    assert any("constant-value test" in issue for issue in issues), (
        f"Expected flag when UPPER_SNAKE compared to literal, got: {issues}"
    )


def test_should_advise_when_scenario_test_omits_flag_its_siblings_patch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    issues = code_rules_enforcer.check_flag_gated_scenario_test_naming(
        _THREE_SIBLINGS_PATCH_THE_FLAG_ONE_SCENARIO_TEST_DOES_NOT,
        SCENARIO_TEST_FILE_PATH,
    )
    advisory_text = capsys.readouterr().err
    assert issues == [], "Advisory check must never add a blocking issue"
    assert "test_should_submit_when_gate_passes" in advisory_text, (
        f"Expected an advisory naming the un-patched scenario test, got: {advisory_text!r}"
    )
    assert "IS_STAGED_VERIFICATION_ENABLED" in advisory_text, (
        f"Expected the advisory to name the established flag, got: {advisory_text!r}"
    )


def test_should_stay_silent_when_scenario_test_patches_the_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = (
        "def test_should_submit_when_gate_passes(monkeypatch) -> None:\n"
        "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
        "    assert run() == 'submitted'\n"
        "\n"
        "def test_should_fail_when_reader_raises(monkeypatch) -> None:\n"
        "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
        "    assert run() == 'failed'\n"
    )
    issues = code_rules_enforcer.check_flag_gated_scenario_test_naming(
        source, SCENARIO_TEST_FILE_PATH
    )
    advisory_text = capsys.readouterr().err
    assert issues == []
    assert advisory_text == "", (
        f"Expected silence when the scenario test patches the flag, got: {advisory_text!r}"
    )


def test_should_stay_silent_when_only_one_sibling_patches_the_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = (
        "def test_should_submit_when_gate_passes(monkeypatch) -> None:\n"
        "    assert run() == 'submitted'\n"
        "\n"
        "def test_should_fail_when_reader_raises(monkeypatch) -> None:\n"
        "    monkeypatch.setattr('pkg.pipeline.IS_STAGED_VERIFICATION_ENABLED', True)\n"
        "    assert run() == 'failed'\n"
    )
    issues = code_rules_enforcer.check_flag_gated_scenario_test_naming(
        source, SCENARIO_TEST_FILE_PATH
    )
    advisory_text = capsys.readouterr().err
    assert issues == []
    assert advisory_text == "", (
        f"One sibling patch is not an established flag; expected silence, got: {advisory_text!r}"
    )


def test_should_not_advise_for_production_file() -> None:
    issues = code_rules_enforcer.check_flag_gated_scenario_test_naming(
        _THREE_SIBLINGS_PATCH_THE_FLAG_ONE_SCENARIO_TEST_DOES_NOT,
        "packages/app/services/submission_pipeline.py",
    )
    assert issues == []


def test_should_flag_test_name_carrying_pre_rename_token() -> None:
    source = (
        "from queue_scan import collect_skip_clean_names\n"
        "\n"
        "def test_collect_skip_theme_names_keeps_only_sorted_at_risk() -> None:\n"
        "    all_skip_names = collect_skip_clean_names(all_assessments)\n"
        "    assert all_skip_names == ['Apple Dawn', 'Zebra Dusk']\n"
    )
    issues = code_rules_enforcer.check_stale_renamed_symbol_in_test_name(
        source, STALE_RENAME_TEST_FILE_PATH
    )
    assert any("collect_skip_theme_names" in issue for issue in issues), (
        f"Expected the stale pre-rename token to be flagged, got: {issues}"
    )
    assert any("collect_skip_clean_names" in issue for issue in issues), (
        f"Expected the issue to name the function actually called, got: {issues}"
    )


def test_should_not_flag_test_name_matching_the_function_it_calls() -> None:
    source = (
        "from queue_scan import collect_skip_clean_names\n"
        "\n"
        "def test_collect_skip_clean_names_keeps_only_sorted_at_risk() -> None:\n"
        "    all_skip_names = collect_skip_clean_names(all_assessments)\n"
        "    assert all_skip_names == ['Apple Dawn', 'Zebra Dusk']\n"
    )
    issues = code_rules_enforcer.check_stale_renamed_symbol_in_test_name(
        source, STALE_RENAME_TEST_FILE_PATH
    )
    assert issues == [], (
        f"A test name matching the called function must not flag, got: {issues}"
    )


def test_should_not_flag_descriptive_test_name_without_a_stale_sibling_token() -> None:
    source = (
        "from queue_scan import collect_skip_clean_names\n"
        "\n"
        "def test_returns_empty_list_when_nothing_is_at_risk() -> None:\n"
        "    assert collect_skip_clean_names([]) == []\n"
    )
    issues = code_rules_enforcer.check_stale_renamed_symbol_in_test_name(
        source, STALE_RENAME_TEST_FILE_PATH
    )
    assert issues == [], (
        f"A descriptive name with no sibling-rename token must not flag, got: {issues}"
    )


def test_should_not_flag_when_the_embedded_token_is_still_referenced() -> None:
    source = (
        "from queue_scan import collect_skip_clean_names, collect_skip_theme_names\n"
        "\n"
        "def test_collect_skip_theme_names_and_clean_names_agree() -> None:\n"
        "    assert collect_skip_clean_names(rows) == collect_skip_theme_names(rows)\n"
    )
    issues = code_rules_enforcer.check_stale_renamed_symbol_in_test_name(
        source, STALE_RENAME_TEST_FILE_PATH
    )
    assert issues == [], (
        f"A token still imported in the file is not stale, got: {issues}"
    )


def test_should_not_flag_stale_token_in_production_file() -> None:
    source = (
        "from queue_scan import collect_skip_clean_names\n"
        "\n"
        "def test_collect_skip_theme_names_keeps_only_sorted_at_risk() -> None:\n"
        "    assert collect_skip_clean_names(rows) == ['Apple Dawn']\n"
    )
    issues = code_rules_enforcer.check_stale_renamed_symbol_in_test_name(
        source, "packages/app/services/queue_scan.py"
    )
    assert issues == [], (
        f"Production files are exempt from the test-name check, got: {issues}"
    )
