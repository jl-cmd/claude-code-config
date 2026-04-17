"""Unit tests for code-rules-enforcer boolean naming-pattern check."""

import importlib.util
import pathlib
import sys


_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIRECTORY / "code-rules-enforcer.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(_hook_module)
check_boolean_naming = _hook_module.check_boolean_naming


PRODUCTION_FILE_PATH = "src/app/feature.py"
TEST_FILE_PATH = "src/app/test_feature.py"


def test_should_flag_boolean_assignment_without_is_prefix() -> None:
    source = "def f() -> None:\n    valid = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert any("valid" in issue for issue in issues)


def test_should_flag_boolean_assignment_without_has_prefix() -> None:
    source = "def f() -> None:\n    permission = False\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert any("permission" in issue for issue in issues)


def test_should_allow_is_prefix() -> None:
    source = "def f() -> None:\n    is_valid = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_has_prefix() -> None:
    source = "def f() -> None:\n    has_permission = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_should_prefix() -> None:
    source = "def f() -> None:\n    should_retry = False\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_can_prefix() -> None:
    source = "def f() -> None:\n    can_edit = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_uppercase_constant_boolean() -> None:
    source = "DEBUG_MODE = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_annotated_boolean_with_valid_prefix() -> None:
    source = "def f() -> None:\n    is_active: bool = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_flag_annotated_boolean_without_prefix() -> None:
    source = "def f() -> None:\n    active: bool = True\n"
    issues = check_boolean_naming(source, PRODUCTION_FILE_PATH)
    assert any("active" in issue for issue in issues)


def test_should_skip_test_files() -> None:
    source = "def f() -> None:\n    valid = True\n"
    issues = check_boolean_naming(source, TEST_FILE_PATH)
    assert issues == []
