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


UNUSED_OPTIONAL_PRODUCTION_FILE_PATH = "packages/app/services/feature.py"
UNUSED_OPTIONAL_TEST_FILE_PATH = "packages/app/tests/test_feature.py"
UNUSED_OPTIONAL_CONFIG_FILE_PATH = "packages/app/config/constants.py"


def test_should_flag_optional_param_never_varied_in_file() -> None:
    source = (
        "def build_url(path: str, prefix: str = '/api') -> str:\n"
        "    return f'{prefix}{path}'\n"
        "\n"
        "def call_first() -> str:\n"
        "    return build_url('/users')\n"
        "\n"
        "def call_second() -> str:\n"
        "    return build_url('/items')\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert any("prefix" in issue for issue in issues), (
        f"Expected 'prefix' flagged as never-varied, got: {issues}"
    )


def test_should_not_flag_when_param_is_varied_at_call_site() -> None:
    source = (
        "def build_url(path: str, prefix: str = '/api') -> str:\n"
        "    return f'{prefix}{path}'\n"
        "\n"
        "def call_with_default() -> str:\n"
        "    return build_url('/users')\n"
        "\n"
        "def call_with_override() -> str:\n"
        "    return build_url('/items', prefix='/v2')\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert not any("prefix" in issue for issue in issues), (
        f"Expected 'prefix' not flagged when varied, got: {issues}"
    )


def test_should_not_flag_unused_optional_in_test_files() -> None:
    source = (
        "def build_url(path: str, prefix: str = '/api') -> str:\n"
        "    return f'{prefix}{path}'\n"
        "\n"
        "def call_first() -> str:\n"
        "    return build_url('/users')\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_TEST_FILE_PATH
    )
    assert issues == [], f"Expected no issues in test file, got: {issues}"


def test_should_not_flag_unused_optional_in_config_files() -> None:
    source = (
        "def build_url(path: str, prefix: str = '/api') -> str:\n"
        "    return f'{prefix}{path}'\n"
        "\n"
        "def call_first() -> str:\n"
        "    return build_url('/users')\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_CONFIG_FILE_PATH
    )
    assert issues == [], f"Expected no issues in config file, got: {issues}"


def test_should_not_flag_when_no_same_file_call_sites_exist() -> None:
    source = (
        "def build_url(path: str, prefix: str = '/api') -> str:\n"
        "    return f'{prefix}{path}'\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Expected no issues when no same-file call sites, got: {issues}"
    )


def test_should_include_line_number_and_param_name_in_issue() -> None:
    source = (
        "def fetch(url: str, timeout: int = 30) -> str:\n"
        "    return get(url, timeout=timeout)\n"
        "\n"
        "def run_fetch() -> str:\n"
        "    return fetch('http://example.com')\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert any("Line 1" in issue and "timeout" in issue for issue in issues), (
        f"Expected issue with line number and param name, got: {issues}"
    )


def test_should_not_flag_when_param_passed_as_exact_default() -> None:
    source = (
        "def fetch(url: str, timeout: int = 30) -> str:\n"
        "    return get(url, timeout=timeout)\n"
        "\n"
        "def run_fetch() -> str:\n"
        "    return fetch('http://example.com', timeout=60)\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert not any("timeout" in issue for issue in issues), (
        f"Expected 'timeout' not flagged when a non-default value is passed, got: {issues}"
    )


INCOMPLETE_MOCK_TEST_FILE_PATH = "packages/app/tests/test_orders.py"
INCOMPLETE_MOCK_PRODUCTION_FILE_PATH = "packages/app/services/orders.py"


def test_should_advise_when_mock_missing_accessed_field(capsys: object) -> None:
    source = (
        "mock_order = {'id': 1}\n"
        "\n"
        "def test_order_total() -> None:\n"
        "    total = mock_order['total']\n"
        "    assert total > 0\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" in captured.err and "total" in captured.err, (
        f"Expected advisory about missing 'total' field, got: {captured.err!r}"
    )


def test_should_not_advise_when_mock_has_all_accessed_fields(capsys: object) -> None:
    source = (
        "mock_order = {'id': 1, 'total': 50}\n"
        "\n"
        "def test_order_total() -> None:\n"
        "    total = mock_order['total']\n"
        "    assert total > 0\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" not in captured.err, (
        f"Expected no advisory when all fields present, got: {captured.err!r}"
    )


def test_should_not_advise_for_incomplete_mocks_in_production_files(capsys: object) -> None:
    source = (
        "mock_order = {'id': 1}\n"
        "\n"
        "def run_order() -> None:\n"
        "    total = mock_order['total']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_PRODUCTION_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" not in captured.err, (
        f"Expected no advisory in production file, got: {captured.err!r}"
    )


def test_should_advise_for_attribute_access_on_mock_object(capsys: object) -> None:
    source = (
        "class MockUser:\n"
        "    pass\n"
        "\n"
        "mock_user = MockUser()\n"
        "mock_user.name = 'Alice'\n"
        "\n"
        "def test_user_email() -> None:\n"
        "    email = mock_user.email\n"
        "    assert email\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_user" in captured.err and "email" in captured.err, (
        f"Expected advisory about missing 'email' attribute, got: {captured.err!r}"
    )


DUPLICATED_FORMAT_PRODUCTION_FILE_PATH = "packages/app/services/api_client.py"
DUPLICATED_FORMAT_TEST_FILE_PATH = "packages/app/tests/test_api_client.py"


def test_should_advise_when_fstring_skeleton_appears_three_or_more_times(capsys: object) -> None:
    source = (
        "def get_user(user_id: str) -> str:\n"
        "    return f'/api/{user_id}'\n"
        "\n"
        "def get_order(order_id: str) -> str:\n"
        "    return f'/api/{order_id}'\n"
        "\n"
        "def get_product(product_id: str) -> str:\n"
        "    return f'/api/{product_id}'\n"
    )
    code_rules_enforcer.check_duplicated_format_patterns(
        source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/api/" in captured.err and "3" in captured.err, (
        f"Expected advisory for repeated /api/<x> pattern, got: {captured.err!r}"
    )


def test_should_not_advise_when_fstring_skeleton_appears_fewer_than_three_times(capsys: object) -> None:
    source = (
        "def get_user(user_id: str) -> str:\n"
        "    return f'/api/{user_id}'\n"
        "\n"
        "def get_order(order_id: str) -> str:\n"
        "    return f'/api/{order_id}'\n"
    )
    code_rules_enforcer.check_duplicated_format_patterns(
        source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/api/" not in captured.err, (
        f"Expected no advisory for pattern appearing only twice, got: {captured.err!r}"
    )


def test_should_not_advise_for_duplicated_format_patterns_in_test_files(capsys: object) -> None:
    source = (
        "def test_user() -> None:\n"
        "    url_a = f'/api/{1}'\n"
        "    url_b = f'/api/{2}'\n"
        "    url_c = f'/api/{3}'\n"
    )
    code_rules_enforcer.check_duplicated_format_patterns(
        source, DUPLICATED_FORMAT_TEST_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/api/" not in captured.err, (
        f"Expected no advisory in test file, got: {captured.err!r}"
    )


def test_should_advise_with_distinct_skeletons(capsys: object) -> None:
    source = (
        "def first(team: str, user: str) -> str:\n"
        "    return f'/teams/{team}/users/{user}'\n"
        "\n"
        "def second(team: str, role: str) -> str:\n"
        "    return f'/teams/{team}/users/{role}'\n"
        "\n"
        "def third(team: str, admin: str) -> str:\n"
        "    return f'/teams/{team}/users/{admin}'\n"
    )
    code_rules_enforcer.check_duplicated_format_patterns(
        source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/teams/" in captured.err, (
        f"Expected advisory for repeated /teams/<x>/users/<x> pattern, got: {captured.err!r}"
    )


def test_should_emit_advisories_for_incomplete_mocks_and_format_patterns_via_validate_content(
    capsys: object,
) -> None:
    incomplete_mock_source = (
        "mock_order = {'id': 1}\n"
        "\n"
        "def test_order_total() -> None:\n"
        "    total = mock_order['total']\n"
        "    assert total > 0\n"
    )
    code_rules_enforcer.validate_content(
        incomplete_mock_source, INCOMPLETE_MOCK_TEST_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" in captured.err and "total" in captured.err, (
        f"Expected incomplete-mock advisory from validate_content, got: {captured.err!r}"
    )

    repeated_pattern_source = (
        "def get_user(user_id: str) -> str:\n"
        "    return f'/api/{user_id}'\n"
        "\n"
        "def get_order(order_id: str) -> str:\n"
        "    return f'/api/{order_id}'\n"
        "\n"
        "def get_product(product_id: str) -> str:\n"
        "    return f'/api/{product_id}'\n"
    )
    code_rules_enforcer.validate_content(
        repeated_pattern_source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/api/" in captured.err and "3" in captured.err, (
        f"Expected duplicated-format advisory from validate_content, got: {captured.err!r}"
    )
