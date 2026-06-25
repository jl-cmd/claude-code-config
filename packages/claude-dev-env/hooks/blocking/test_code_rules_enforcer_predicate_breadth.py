"""Tests for check_predicate_exact_count_name_breadth — Category O6 predicate breadth.

A boolean helper named for an exact cardinal of a countable noun
(``_call_node_builds_two_argument_range``) promises that exact count, while a body
that tests ``len(...) >= 2`` also accepts a broader input class. The name promises
an exact count the body does not enforce — the deterministic slice of Category O6
predicate-breadth docstring-vs-implementation drift for an exact-count name over an
open-ended length body.
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


def check_predicate_exact_count_name_breadth(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_predicate_exact_count_name_breadth(content, file_path)


PRODUCTION_FILE_PATH = "/project/scripts/code_rules_docstrings.py"
TEST_FILE_PATH = "/project/scripts/test_code_rules_docstrings.py"


def test_flags_two_argument_name_with_open_ended_length_body() -> None:
    content = (
        "import ast\n"
        "def _call_node_builds_two_argument_range(call_node: ast.Call) -> bool:\n"
        "    callee = call_node.func\n"
        "    return (\n"
        "        isinstance(callee, ast.Name)\n"
        '        and callee.id == "range"\n'
        "        and len(call_node.args) >= 2\n"
        "    )\n"
    )
    issues = check_predicate_exact_count_name_breadth(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "_call_node_builds_two_argument_range" in issues[0]


def test_passes_when_body_tests_length_with_equality() -> None:
    content = (
        "import ast\n"
        "def _call_node_builds_two_argument_range(call_node: ast.Call) -> bool:\n"
        "    return len(call_node.args) == 2\n"
    )
    assert check_predicate_exact_count_name_breadth(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_name_has_no_cardinal_noun_pair() -> None:
    content = (
        "import ast\n"
        "def _call_has_enough_args(call_node: ast.Call) -> bool:\n"
        "    return len(call_node.args) >= 2\n"
    )
    assert check_predicate_exact_count_name_breadth(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_cardinal_precedes_a_non_countable_noun() -> None:
    content = (
        "def _uses_two_factor_auth(account_factors: list[str]) -> bool:\n"
        "    return len(account_factors) >= 2\n"
    )
    assert check_predicate_exact_count_name_breadth(content, PRODUCTION_FILE_PATH) == []


def test_passes_for_non_boolean_return() -> None:
    content = (
        "def _take_two_items(all_values: list[int]) -> list[int]:\n"
        "    if len(all_values) >= 2:\n"
        "        return all_values\n"
        "    return all_values\n"
    )
    assert check_predicate_exact_count_name_breadth(content, PRODUCTION_FILE_PATH) == []


def test_flags_three_element_name_with_greater_than_length_body() -> None:
    content = (
        "def _builds_three_element_tuple(all_parts: list[str]) -> bool:\n"
        "    return len(all_parts) > 2\n"
    )
    assert len(check_predicate_exact_count_name_breadth(content, PRODUCTION_FILE_PATH)) == 1


def test_test_files_are_exempt() -> None:
    content = (
        "import ast\n"
        "def _call_node_builds_two_argument_range(call_node: ast.Call) -> bool:\n"
        "    return len(call_node.args) >= 2\n"
    )
    assert check_predicate_exact_count_name_breadth(content, TEST_FILE_PATH) == []


def test_issue_count_is_capped() -> None:
    one_predicate = (
        "def _builds_two_argument_{suffix}(all_args: list[int]) -> bool:\n"
        "    return len(all_args) >= 2\n"
    )
    content = "".join(one_predicate.format(suffix=each_suffix) for each_suffix in "abcde")
    assert len(check_predicate_exact_count_name_breadth(content, PRODUCTION_FILE_PATH)) == 3
