"""Tests covering file-global constant reference resolution edge cases.

Loop2-C: class-decorator usage of a module-level constant must count as a
caller so the single-caller rule fires correctly.

Loop2-D: module-scope usages must register as a distinct caller bucket so
the "zero function references" exemption does not swallow real references.
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


PRODUCTION_FILE_PATH = "packages/claude-dev-env/hooks/blocking/example_production.py"


def test_should_flag_constant_used_only_in_class_level_decorator() -> None:
    source = (
        "TIMEOUT = 5\n"
        "\n"
        "def register(value):\n"
        "    def wrap(cls):\n"
        "        return cls\n"
        "    return wrap\n"
        "\n"
        "@register(TIMEOUT)\n"
        "class Foo:\n"
        "    pass\n"
    )
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert any(
        "TIMEOUT" in issue and "only 1 function/method" in issue for issue in issues
    ), f"Expected class-decorator usage to register as a caller, got: {issues}"


def test_should_flag_constant_used_once_at_module_scope_and_once_in_function() -> None:
    source = "UPPER = 1\nSHADOW = UPPER\n\ndef lonely_caller():\n    return UPPER\n"
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Expected module-scope + function usage to count as 2 distinct callers, got: {issues}"
    )


def test_should_not_export_config_path_patterns_constant() -> None:
    assert not hasattr(code_rules_enforcer, "CONFIG_PATH_PATTERNS"), (
        "CONFIG_PATH_PATTERNS is dead code after is_config_file() was rewritten"
        " with pathlib parts matching; it must be removed"
    )


def test_advisory_should_not_flag_class_attribute_after_method_def() -> None:
    source_with_class_attribute_after_method = (
        "class ExampleModel:\n"
        "    def method_a(self) -> None:\n"
        "        pass\n"
        "\n"
        "    TABLE_NAME = \"example\"\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_class_attribute_after_method,
        "example_module.py",
    )
    assert advisory_issues == [], (
        "Class-level TABLE_NAME attribute must not be flagged as function-local"
    )


def test_advisory_should_still_flag_actual_method_body_constant() -> None:
    source_with_method_body_constant = (
        "class ExampleModel:\n"
        "    def method_a(self) -> None:\n"
        "        MAXIMUM_RETRIES = 3\n"
        "        return None\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_method_body_constant,
        "example_module.py",
    )
    assert len(advisory_issues) == 1, (
        "Method-body UPPER_SNAKE constant must still surface as advisory"
    )
    assert "MAXIMUM_RETRIES" in advisory_issues[0]


def test_advisory_cap_matches_max_issues_per_check_constant() -> None:
    many_constants_source = (
        "def crowded_function():\n"
        "    ALPHA_CONSTANT = 1\n"
        "    BETA_CONSTANT = 2\n"
        "    GAMMA_CONSTANT = 3\n"
        "    DELTA_CONSTANT = 4\n"
        "    EPSILON_CONSTANT = 5\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        many_constants_source,
        "example_module.py",
    )
    assert len(advisory_issues) == code_rules_enforcer.MAX_ISSUES_PER_CHECK, (
        "Advisory cap must equal MAX_ISSUES_PER_CHECK, not a hardcoded literal"
    )


def test_advisory_should_flag_outer_constants_after_nested_def() -> None:
    source_with_nested_def = (
        "def outer():\n"
        "    OUTER_CONST = 1\n"
        "    def inner():\n"
        "        INNER_CONST = 2\n"
        "    ANOTHER_OUTER = 3\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_nested_def,
        "example_module.py",
    )
    flagged_names = " ".join(advisory_issues)
    assert "OUTER_CONST" in flagged_names, (
        "OUTER_CONST before nested def must be flagged"
    )
    assert "INNER_CONST" in flagged_names, (
        "INNER_CONST inside nested def must be flagged"
    )
    assert "ANOTHER_OUTER" in flagged_names, (
        "ANOTHER_OUTER after nested def must be flagged — this is the regression case"
    )
