"""Unit tests for banned-identifier check in code-rules-enforcer hook."""

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
check_banned_identifiers = hook_module.check_banned_identifiers

PRODUCTION_FILE_PATH = "packages/app/services/loader.py"
TEST_FILE_PATH = "packages/app/services/test_loader.py"


def test_should_flag_result_assignment() -> None:
    content = "def load():\n    result = compute()\n    return result\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("result" in issue for issue in issues)


def test_should_flag_data_assignment() -> None:
    content = "def fetch():\n    data = read()\n    return data\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("data" in issue for issue in issues)


def test_should_flag_output_assignment() -> None:
    content = "def render():\n    output = build()\n    return output\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("output" in issue for issue in issues)


def test_should_flag_response_assignment() -> None:
    content = "def call():\n    response = send()\n    return response\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("response" in issue for issue in issues)


def test_should_flag_value_assignment() -> None:
    content = "def read():\n    value = lookup()\n    return value\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("value" in issue for issue in issues)


def test_should_flag_item_assignment() -> None:
    content = "def pick():\n    item = first()\n    return item\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("item" in issue for issue in issues)


def test_should_flag_temp_assignment() -> None:
    content = "def swap():\n    temp = holder()\n    return temp\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("temp" in issue for issue in issues)


def test_should_flag_annotated_assignment() -> None:
    content = "def build() -> dict:\n    data: dict = {}\n    return data\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("data" in issue for issue in issues)


def test_should_not_flag_descriptive_names() -> None:
    content = (
        "def summarize_orders():\n"
        "    all_users = load_users()\n"
        "    is_valid = True\n"
        "    price_by_product = {}\n"
        "    for each_order in all_users:\n"
        "        pass\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_not_flag_name_containing_banned_substring() -> None:
    content = (
        "def aggregate():\n"
        "    result_set = fetch()\n"
        "    data_map = {}\n"
        "    value_counts = []\n"
        "    return result_set, data_map, value_counts\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_skip_test_files() -> None:
    content = "def test_thing():\n    result = compute()\n    assert result\n"
    issues = check_banned_identifiers(content, TEST_FILE_PATH)
    assert issues == []


def test_should_skip_hook_infrastructure() -> None:
    hook_path = "/home/user/.claude/hooks/some-hook.py"
    content = "def run():\n    data = gather()\n    return data\n"
    issues = check_banned_identifiers(content, hook_path)
    assert issues == []


def test_should_cap_at_three_issues() -> None:
    content = (
        "def many_bad():\n"
        "    result = 1\n"
        "    data = 2\n"
        "    output = 3\n"
        "    response = 4\n"
        "    value = 5\n"
        "    return result\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 3


def test_should_include_line_number_and_name() -> None:
    content = "def run():\n    result = 1\n    return result\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "Line 2" in issues[0]
    assert "'result'" in issues[0]


def test_should_handle_syntax_error_gracefully() -> None:
    content = "def broken(\n    this is not python\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert issues == []
