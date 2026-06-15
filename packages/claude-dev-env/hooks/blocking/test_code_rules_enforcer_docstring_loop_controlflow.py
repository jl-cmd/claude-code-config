"""Tests for check_docstring_loop_control_flow_claims.

A docstring that asserts a loop "breaks out of each loop the moment" a step
runs, or that on a failure the loop "falls through to the next entry", makes a
checkable claim about the function's loop control flow. The unconditional-break
claim is false when every ``break`` that ends a loop is conditional — guarded by
an ``if`` test, sitting under a guarded ``case``, or living in an ``except``
handler. The fall-through claim is false only when every loop processes each
entry straight through with no skip path: no ``continue``, no ``if``, and no
``match``. A break inside a wildcard ``case _:`` always fires, so it satisfies
the unconditional-break claim; an ``if``-guarded branch is itself a skip path,
so it satisfies the fall-through claim.

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


def test_should_not_flag_fall_through_claim_when_loop_has_guarded_break() -> None:
    issues = check_docstring_loop_control_flow_claims(
        _conditional_break_only_source(), PRODUCTION_FILE_PATH
    )
    assert not any("fall through" in each for each in issues), (
        "An if-guarded break is itself a skip path that lets control reach the "
        f"next iteration, so the fall-through claim is accurate, got: {issues!r}"
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


def test_should_not_flag_fall_through_claim_when_loop_has_conditional_skip_path() -> None:
    source = (
        "def budgeted_seconds() -> int:\n"
        '    """Return the budget for the happy path.\n'
        "\n"
        "    A failed command makes the loop fall through to the next entry.\n"
        '    """\n'
        "    for each_command in all_commands:\n"
        "        run = invoke(each_command)\n"
        "        if run.returncode == 0:\n"
        "            record(run)\n"
        "    return budget\n"
    )
    issues = check_docstring_loop_control_flow_claims(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "A loop whose conditional branch lets control reach the next iteration "
        f"satisfies a fall-through claim, got: {issues!r}"
    )


def test_should_flag_fall_through_claim_when_loop_processes_every_entry() -> None:
    source = (
        "def budgeted_seconds() -> int:\n"
        '    """Return the budget for the happy path.\n'
        "\n"
        "    Each iteration makes the loop fall through to the next entry.\n"
        '    """\n'
        "    for each_command in all_commands:\n"
        "        run = invoke(each_command)\n"
        "        record(run)\n"
        "    return budget\n"
    )
    issues = check_docstring_loop_control_flow_claims(source, PRODUCTION_FILE_PATH)
    assert any("fall through" in each for each in issues), (
        "A loop that unconditionally processes every entry with no skip path "
        f"contradicts a fall-through claim, got: {issues!r}"
    )


def test_should_not_flag_unconditional_break_claim_when_break_is_in_wildcard_case() -> None:
    source = (
        "def budgeted_seconds() -> int:\n"
        '    """Return the budget for the happy path.\n'
        "\n"
        "    The branch breaks out of each loop the moment a step runs.\n"
        '    """\n'
        "    for each_command in all_commands:\n"
        "        invoke(each_command)\n"
        "        match each_command:\n"
        "            case _:\n"
        "                break\n"
        "    return budget\n"
    )
    issues = check_docstring_loop_control_flow_claims(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "A break inside a wildcard match case always fires, so the "
        f"unconditional-break claim is accurate, got: {issues!r}"
    )


def test_should_flag_unconditional_break_claim_when_match_has_no_wildcard() -> None:
    source = (
        "def budgeted_seconds() -> int:\n"
        '    """Return the budget for the happy path.\n'
        "\n"
        "    The branch breaks out of each loop the moment a step runs.\n"
        '    """\n'
        "    for each_command in all_commands:\n"
        "        invoke(each_command)\n"
        "        match each_command:\n"
        "            case _ if is_done(each_command):\n"
        "                break\n"
        "    return budget\n"
    )
    issues = check_docstring_loop_control_flow_claims(source, PRODUCTION_FILE_PATH)
    assert any("breaks out of each loop" in each for each in issues), (
        "A guarded match case only breaks conditionally, so the false "
        f"unconditional-break claim must still flag, got: {issues!r}"
    )


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
