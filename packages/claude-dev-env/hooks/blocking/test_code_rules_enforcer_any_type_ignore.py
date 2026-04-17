"""Unit tests for code-rules-enforcer Any/type-ignore checks."""

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIR / "code-rules-enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
check_type_escape_hatches = hook_module.check_type_escape_hatches

PRODUCTION_FILE_PATH = "/project/src/module.py"
TEST_FILE_PATH = "/project/src/test_module.py"


def test_should_flag_any_parameter_annotation() -> None:
    source = "def foo(x: Any) -> None:\n    pass\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("Any" in issue for issue in issues)


def test_should_flag_any_return_annotation() -> None:
    source = "def foo() -> Any:\n    return None\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("Any" in issue for issue in issues)


def test_should_flag_any_variable_annotation() -> None:
    source = "x: Any = 1\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("Any" in issue for issue in issues)


def test_should_flag_any_inside_optional() -> None:
    source = "from typing import Optional\nx: Optional[Any] = None\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("Any" in issue for issue in issues)


def test_should_allow_lowercase_any_as_builtin_call() -> None:
    source = "items = [1, 2, 3]\nif any(x > 0 for x in items):\n    pass\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert not any("Any" in issue or "any" in issue for issue in issues)


def test_should_flag_bare_type_ignore() -> None:
    source = "x = 1  # type: ignore\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("type: ignore" in issue for issue in issues)


def test_should_flag_coded_type_ignore_without_justification() -> None:
    source = "x = 1  # type: ignore[misc]\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("type: ignore" in issue for issue in issues)


def test_should_allow_justified_type_ignore() -> None:
    source = "x = 1  # type: ignore[misc]  # stubs missing in foo library\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert not any("type: ignore" in issue for issue in issues)


def test_should_skip_test_files() -> None:
    source = "def foo(x: Any) -> Any:\n    y: Any = 1  # type: ignore\n    return y\n"
    issues = check_type_escape_hatches(source, TEST_FILE_PATH)
    assert issues == []
