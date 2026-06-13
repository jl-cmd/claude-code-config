"""Tests for check_docstring_loop_control_flow_claims.

A docstring that asserts a loop "breaks out of each loop the moment" a step
runs, or that on a failure the loop "falls through to the next entry", makes a
checkable claim about the function's loop control flow. When every ``break`` in
the function's loops is conditional (guarded by an ``if`` test or living in an
``except`` handler) the unconditional-break claim is false, and when the loops
contain no ``continue`` the fall-through claim is false. Both phrasings are the
ones a reviewer flagged on a budget-estimating helper whose loops break only on
success and only continue on a missing command.

Exemptions match the sibling docstring checks: private/dunder names,
exempt decorators, trivial bodies, test files, and hook infrastructure.
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


def check_docstring_loop_control_flow_claims(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_loop_control_flow_claims(content, file_path)


PRODUCTION_FILE_PATH = "/project/src/services.py"
TEST_FILE_PATH = "/project/src/test_services.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _conditional_break_only_source() -> str:
    return (
        "def budgeted_seconds() -> int:\n"
        '    """Return the budget for the happy path.\n'
        "\n"
        "    The branch breaks out of each loop the moment a command runs, so a\n"
        "    timeout makes the loops fall through to the next entry.\n"
        '    """\n'
        "    for each_command in all_commands:\n"
        "        run = invoke(each_command)\n"
        "        if run.returncode == 0:\n"
        "            break\n"
        "    return budget\n"
    )


def test_should_flag_unconditional_break_claim_when_break_is_conditional() -> None:
    issues = check_docstring_loop_control_flow_claims(
        _conditional_break_only_source(), PRODUCTION_FILE_PATH
    )
    assert any("breaks out of each loop" in each for each in issues), (
        f"Expected the false unconditional-break claim to be flagged, got: {issues!r}"
    )


def test_should_flag_fall_through_claim_when_loop_has_no_continue() -> None:
    issues = check_docstring_loop_control_flow_claims(
        _conditional_break_only_source(), PRODUCTION_FILE_PATH
    )
    assert any("fall through" in each for each in issues), (
        f"Expected the false fall-through claim to be flagged, got: {issues!r}"
    )


def test_should_not_flag_when_break_is_unconditional() -> None:
    source = (
        "def budgeted_seconds() -> int:\n"
        '    """Return the budget for the happy path.\n'
        "\n"
        "    The branch breaks out of each loop the moment a command runs.\n"
        '    """\n'
        "    for each_command in all_commands:\n"
        "        invoke(each_command)\n"
        "        break\n"
        "    return budget\n"
    )
    issues = check_docstring_loop_control_flow_claims(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"A truly unconditional break must not be flagged, got: {issues!r}"


def test_should_not_flag_fall_through_claim_when_loop_has_continue() -> None:
    source = (
        "def budgeted_seconds() -> int:\n"
        '    """Return the budget for the happy path.\n'
        "\n"
        "    A missing command makes the loop fall through to the next entry.\n"
        '    """\n'
        "    for each_command in all_commands:\n"
        "        if is_missing(each_command):\n"
        "            continue\n"
        "        invoke(each_command)\n"
        "    return budget\n"
    )
    issues = check_docstring_loop_control_flow_claims(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"A real continue-driven fall-through must not be flagged, got: {issues!r}"


def test_should_not_flag_docstring_without_loop_control_claim() -> None:
    source = (
        "def budgeted_seconds() -> int:\n"
        '    """Return the wall-clock budget for the happy path."""\n'
        "    for each_command in all_commands:\n"
        "        run = invoke(each_command)\n"
        "        if run.returncode == 0:\n"
        "            break\n"
        "    return budget\n"
    )
    issues = check_docstring_loop_control_flow_claims(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A docstring with no loop-control claim must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_function_without_loops() -> None:
    source = (
        "def budgeted_seconds() -> int:\n"
        '    """Return the budget; this breaks out of each loop immediately."""\n'
        "    fix_phase = TIMEOUT\n"
        "    format_phase = TIMEOUT\n"
        "    return fix_phase + format_phase\n"
    )
    issues = check_docstring_loop_control_flow_claims(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A loopless function carries no loop control flow to contradict, got: {issues!r}"
    )


def test_should_skip_private_function() -> None:
    issues = check_docstring_loop_control_flow_claims(
        _conditional_break_only_source().replace("def budgeted_seconds", "def _budgeted_seconds"),
        PRODUCTION_FILE_PATH,
    )
    assert issues == [], f"Private functions exempt, got: {issues!r}"


def test_should_skip_test_file() -> None:
    issues = check_docstring_loop_control_flow_claims(
        _conditional_break_only_source(), TEST_FILE_PATH
    )
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_docstring_loop_control_flow_claims(
        _conditional_break_only_source(), HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_docstring_loop_control_flow_claims("def fetch(\n", PRODUCTION_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"
