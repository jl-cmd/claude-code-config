"""Tests covering file-global constant reference resolution edge cases.

Loop2-C: class-decorator usage of a module-level constant must count as a
caller so the single-caller rule fires correctly.

Loop2-D: module-scope usages must register as a distinct caller bucket so
the "zero function references" exemption does not swallow real references.
"""

from __future__ import annotations

import importlib.util
import sys
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

_BLOCKING_DIR = Path(__file__).resolve().parent
if str(_BLOCKING_DIR) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIR))

from code_rules_path_utils import is_config_file as path_utils_is_config_file  # noqa: E402

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


def test_should_flag_when_every_call_passes_the_exact_default() -> None:
    source = (
        "def fetch(url: str, timeout: int = 30) -> str:\n"
        "    return get(url, timeout=timeout)\n"
        "\n"
        "def run_fetch() -> str:\n"
        "    return fetch('http://example.com', timeout=30)\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, UNUSED_OPTIONAL_PRODUCTION_FILE_PATH
    )
    assert any("timeout" in issue for issue in issues), (
        f"Expected 'timeout' flagged when every call passes the exact default, got: {issues}"
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


CONSTANT_EQUALITY_TEST_FILE_PATH = "packages/app/tests/test_constants.py"


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


NESTED_FUNCTION_PRODUCTION_FILE_PATH = "packages/app/services/nested.py"


def test_should_not_flag_nested_function_optional_param() -> None:
    source = (
        "def outer() -> None:\n"
        "    def inner(timeout: int = 30) -> None:\n"
        "        pass\n"
        "    inner()\n"
        "    inner()\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, NESTED_FUNCTION_PRODUCTION_FILE_PATH
    )
    assert not any("timeout" in issue for issue in issues), (
        f"Expected nested function 'timeout' not flagged, got: {issues}"
    )


def test_should_advise_when_mock_defined_inside_test_function_is_incomplete(
    capsys: object,
) -> None:
    source = (
        "def test_thing() -> None:\n"
        "    mock_user = {'name': 'x'}\n"
        "    assert mock_user['email'] == 'y'\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, INCOMPLETE_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    assert "mock_user" in captured.err and "email" in captured.err, (
        f"Expected advisory for mock defined inside test function, got: {captured.err!r}"
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


SCOPE_KEYED_MOCK_TEST_FILE_PATH = "packages/app/tests/test_scope_mocks.py"
KWARGS_EXPANSION_PRODUCTION_FILE_PATH = "packages/app/services/fetcher.py"


def test_should_check_each_scope_mock_against_its_own_field_set(capsys: object) -> None:
    """Same mock_user name in two test functions with different field sets.

    First function defines mock_user with only 'id'; accesses 'email' — should warn.
    Second function defines mock_user with 'id' and 'email'; accesses 'email' — no warn.
    The second definition must NOT overwrite the first scope's tracking.
    """
    source = (
        "def test_first_scope() -> None:\n"
        "    mock_user = {'id': 1}\n"
        "    email = mock_user['email']\n"
        "\n"
        "def test_second_scope() -> None:\n"
        "    mock_user = {'id': 2, 'email': 'b@b.com'}\n"
        "    email = mock_user['email']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, SCOPE_KEYED_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        f"Expected exactly 1 advisory (first scope missing email), got: {captured.err!r}"
    )


def test_should_emit_exactly_one_advisory_for_repeated_accesses_to_same_missing_field(
    capsys: object,
) -> None:
    """mock_user accessed 5 times for 'email' but email is missing — emit exactly one advisory."""
    source = (
        "def test_repeated_access() -> None:\n"
        "    mock_user = {'id': 1}\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
        "    _ = mock_user['email']\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, SCOPE_KEYED_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        f"Expected exactly 1 advisory for 5 repeated accesses to missing 'email', got: {captured.err!r}"
    )


def test_should_not_flag_optional_param_when_only_call_site_uses_kwargs_expansion() -> None:
    """A call using **defaults passes unknown values — the param must NOT be flagged."""
    source = (
        "def fetch(url: str, timeout: int = 30) -> str:\n"
        "    return url\n"
        "\n"
        "def run() -> str:\n"
        "    defaults = {'timeout': 30}\n"
        "    return fetch('http://example.com', **defaults)\n"
    )
    issues = code_rules_enforcer.check_unused_optional_parameters(
        source, KWARGS_EXPANSION_PRODUCTION_FILE_PATH
    )
    assert not any("timeout" in issue for issue in issues), (
        f"Expected 'timeout' NOT flagged when call uses **kwargs expansion, got: {issues}"
    )


MODULE_LEVEL_MOCK_TEST_FILE_PATH = "packages/app/tests/test_module_level.py"


def test_should_emit_exactly_one_advisory_for_module_level_mock_with_missing_field(
    capsys: object,
) -> None:
    """Module-level mock_user with one missing field access should produce ONE advisory.

    Finding 4: ast.walk() already yields the root Module node, so
    [module_tree, *ast.walk(module_tree)] iterates the module twice and
    previously produced two identical advisories for module-level mocks.
    """
    source = (
        "mock_user = {'name': 'Alice'}\n"
        "\n"
        "def test_email_present() -> None:\n"
        "    email = mock_user['email']\n"
        "    assert email\n"
    )
    code_rules_enforcer.check_incomplete_mocks(source, MODULE_LEVEL_MOCK_TEST_FILE_PATH)
    captured = getattr(capsys, "readouterr")()
    advisory_lines = [
        line for line in captured.err.splitlines() if "mock_user" in line and "email" in line
    ]
    assert len(advisory_lines) == 1, (
        f"Expected exactly 1 advisory for module-level mock missing 'email', got: {captured.err!r}"
    )


def test_is_config_file_rejects_filename_only_config_pattern() -> None:
    """Paths where 'config' appears only in the filename (not as a directory segment) must return False."""
    assert code_rules_enforcer.is_config_file("scripts/db/config.py") is False, (
        "scripts/db/config.py — filename is config.py but parent dir is db, must be False"
    )
    assert code_rules_enforcer.is_config_file("lib/myconfig.py") is False, (
        "lib/myconfig.py — config appears only in the filename stem, must be False"
    )
    assert code_rules_enforcer.is_config_file("src/app_config.py") is False, (
        "src/app_config.py — config appears only in the filename stem, must be False"
    )


def test_is_config_file_via_path_utils_returns_same_results_as_enforcer() -> None:
    """is_config_file from code_rules_path_utils must agree with the enforcer on all sample paths."""
    all_sample_paths = [
        "scripts/db/config.py",
        "config/timing.py",
        "settings.py",
    ]
    for each_path in all_sample_paths:
        enforcer_result = code_rules_enforcer.is_config_file(each_path)
        path_utils_result = path_utils_is_config_file(each_path)
        assert enforcer_result == path_utils_result, (
            f"is_config_file diverged for {each_path!r}: "
            f"enforcer={enforcer_result}, code_rules_path_utils={path_utils_result}"
        )


def test_is_exempt_for_advisory_scan_returns_true_for_config_file() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("project/config/constants.py") is True


def test_is_exempt_for_advisory_scan_returns_true_for_test_file() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("test_example.py") is True


def test_is_exempt_for_advisory_scan_returns_true_for_workflow_registry() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("app/workflow/states.py") is True


def test_is_exempt_for_advisory_scan_returns_true_for_migration() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("app/migrations/0001_initial.py") is True


def test_is_exempt_for_advisory_scan_returns_false_for_production_file() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("packages/myapp/some_module.py") is False


def test_scan_function_body_constants_finds_upper_snake_in_function() -> None:
    source = (
        "def fetch():\n"
        "    MAX_RETRIES = 3\n"
        "    for attempt in range(MAX_RETRIES):\n"
        "        pass\n"
    )
    advisory_issues = code_rules_enforcer._scan_function_body_constants(source)
    assert any("MAX_RETRIES" in issue for issue in advisory_issues)


def test_scan_function_body_constants_does_not_flag_module_level() -> None:
    source = "MAX_RETRIES = 3\n\ndef fetch():\n    pass\n"
    advisory_issues = code_rules_enforcer._scan_function_body_constants(source)
    assert advisory_issues == []


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
