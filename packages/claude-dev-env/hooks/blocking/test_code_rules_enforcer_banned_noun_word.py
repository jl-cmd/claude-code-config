"""Tests for ``check_banned_noun_word_boundary``.

Pattern class: identifiers embedding a CODE_RULES §5 banned noun word
(``result``, ``data``, ``output``, ``response``, ``value``, ``item``,
``temp``) as a snake_case word part or camelCase word part inside a longer
identifier, even when the exact-match check would let them through. Cited
SYNTHESIS evidence: pa#143 F8 (``OUTPUT`` constant), pa#144 F19
(``HolidayPeakResult`` class), pa#143 F13 (``canned_results`` collection),
pa#136 F35 (snake_case variants).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIR / "code_rules_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
check_banned_noun_word_boundary = hook_module.check_banned_noun_word_boundary
check_banned_identifiers = hook_module.check_banned_identifiers
validate_content = hook_module.validate_content
_identifier_word_parts = hook_module._identifier_word_parts
_find_banned_noun_word = hook_module._find_banned_noun_word

PRODUCTION_FILE_PATH = "packages/app/services/customer_pipeline.py"
TEST_FILE_PATH = "packages/app/services/test_customer_pipeline.py"
CONFIG_FILE_PATH = "packages/app/config/constants.py"
HOOK_INFRASTRUCTURE_PATH = "/packages/claude-dev-env/hooks/blocking/example.py"


def test_should_split_snake_case_identifier_into_lowercase_words() -> None:
    assert _identifier_word_parts("canned_results") == ["canned", "results"]


def test_should_split_camel_case_identifier_into_lowercase_words() -> None:
    assert _identifier_word_parts("HolidayPeakResult") == ["holiday", "peak", "result"]


def test_should_split_screaming_snake_case_into_lowercase_words() -> None:
    assert _identifier_word_parts("SAFE_OUTPUT_PATH") == ["safe", "output", "path"]


def test_should_treat_consecutive_capitals_as_acronym_word() -> None:
    assert _identifier_word_parts("XMLParser") == ["xml", "parser"]


def test_should_return_no_banned_word_for_clean_identifier() -> None:
    assert _find_banned_noun_word("customer_pipeline") is None


def test_should_return_banned_word_for_camel_case_with_result_suffix() -> None:
    assert _find_banned_noun_word("HolidayPeakResult") == "result"


def test_should_return_banned_word_for_snake_case_with_results_plural() -> None:
    assert _find_banned_noun_word("canned_results") == "results"


def test_should_return_banned_word_for_screaming_snake_with_output() -> None:
    assert _find_banned_noun_word("SAFE_OUTPUT_PATH") == "output"


def test_should_flag_class_name_containing_result_word() -> None:
    source = "class HolidayPeakResult:\n    pass\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("HolidayPeakResult" in each_issue for each_issue in issues)


def test_should_flag_module_level_constant_with_output_word() -> None:
    source = "SAFE_OUTPUT_PATH = '/tmp/x'\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("SAFE_OUTPUT_PATH" in each_issue for each_issue in issues)


def test_should_flag_local_variable_with_results_word() -> None:
    source = (
        "def aggregate() -> list[int]:\n    canned_results = [1, 2, 3]\n    return canned_results\n"
    )
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("canned_results" in each_issue for each_issue in issues)


def test_should_flag_function_parameter_with_response_word() -> None:
    source = (
        "def handle(cached_response: dict[str, int]) -> int:\n    return len(cached_response)\n"
    )
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("cached_response" in each_issue for each_issue in issues)


def test_should_not_flag_exact_match_banned_identifier() -> None:
    source = "result = compute()\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_not_flag_dunder_method_with_banned_word() -> None:
    source = "class Foo:\n    def __init_data__(self) -> None: pass\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_skip_test_files() -> None:
    source = "class HolidayPeakResult:\n    pass\n"
    issues = check_banned_noun_word_boundary(source, TEST_FILE_PATH)
    assert issues == []


def test_should_skip_config_files() -> None:
    source = "OUTPUT_DIR = '/tmp'\n"
    issues = check_banned_noun_word_boundary(source, CONFIG_FILE_PATH)
    assert issues == []


def test_should_skip_hook_infrastructure() -> None:
    source = "OUTPUT_DIR = '/tmp'\n"
    issues = check_banned_noun_word_boundary(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == []


def test_should_skip_when_source_does_not_parse() -> None:
    source = "def broken(:\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_flag_response_count_parameter_on_method() -> None:
    source = "class Foo:\n    def bar(self, response_count: int) -> None: pass\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("response_count" in each_issue for each_issue in issues)


def test_should_include_banned_word_in_message() -> None:
    source = "PEAK_OUTPUTS = []\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert issues
    assert "outputs" in issues[0]


def test_should_cap_issue_count_at_configured_maximum() -> None:
    source = (
        "AAA_RESULT_PATH = 'a'\n"
        "BBB_RESULT_PATH = 'b'\n"
        "CCC_RESULT_PATH = 'c'\n"
        "DDD_RESULT_PATH = 'd'\n"
        "EEE_RESULT_PATH = 'e'\n"
    )
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert len(issues) == hook_module.MAX_BANNED_NOUN_WORD_ISSUES


def test_should_flag_function_definition_with_data_word_in_name() -> None:
    source = "def fetch_data_table() -> None:\n    pass\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("fetch_data_table" in each_issue for each_issue in issues)


def test_should_flag_import_from_alias_with_banned_word() -> None:
    source = "from models import HolidayPeakResult\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("HolidayPeakResult" in each_issue for each_issue in issues)


def test_should_flag_import_renamed_with_banned_word() -> None:
    source = "import legacy_helper as cached_response\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("cached_response" in each_issue for each_issue in issues)


def test_should_skip_star_import_with_no_named_binding() -> None:
    source = "from models import *\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_use_only_first_segment_of_dotted_import_name() -> None:
    source = "import analytics.data_pipeline\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_flag_dotted_import_when_first_segment_has_banned_word() -> None:
    source = "import data_pipeline.analytics\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("data_pipeline" in each_issue for each_issue in issues)


def test_should_flag_with_as_binding_target_with_banned_word() -> None:
    source = (
        "def load_payload() -> str:\n"
        "    with open('payload.json') as data_result:\n"
        "        return data_result.read()\n"
    )
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("data_result" in each_issue for each_issue in issues)


EDIT_FRAGMENT_WITHOUT_BANNED_NAME = (
    "def compute_total() -> int:\n    running_sum = 0\n    return running_sum\n"
)
FULL_FILE_WITH_BANNED_NAME_OUTSIDE_FRAGMENT = (
    "def compute_total() -> int:\n    running_sum = 0\n    return running_sum\n"
    "\n"
    "def aggregate() -> list[int]:\n"
    "    canned_results = [4, 5, 6]\n"
    "    return canned_results\n"
)


def test_edit_scope_matches_companion_banned_identifier_check() -> None:
    fragment_noun_issues = check_banned_noun_word_boundary(
        EDIT_FRAGMENT_WITHOUT_BANNED_NAME, PRODUCTION_FILE_PATH
    )
    fragment_exact_issues = check_banned_identifiers(
        EDIT_FRAGMENT_WITHOUT_BANNED_NAME, PRODUCTION_FILE_PATH
    )
    noun_issues = validate_content(
        EDIT_FRAGMENT_WITHOUT_BANNED_NAME,
        PRODUCTION_FILE_PATH,
        old_content="",
        full_file_content=FULL_FILE_WITH_BANNED_NAME_OUTSIDE_FRAGMENT,
    )
    assert fragment_noun_issues == []
    assert fragment_exact_issues == []
    assert not any("canned_results" in each_issue for each_issue in noun_issues), (
        "check_banned_noun_word_boundary must analyze the edited fragment scope "
        "on an Edit (matching check_banned_identifiers), not the reconstructed "
        f"full file; got {noun_issues!r}"
    )


def test_edit_scope_still_flags_banned_word_inside_fragment() -> None:
    fragment_with_banned_word = (
        "def aggregate() -> list[int]:\n"
        "    canned_results = [4, 5, 6]\n"
        "    return canned_results\n"
    )
    full_file = EDIT_FRAGMENT_WITHOUT_BANNED_NAME + "\n" + fragment_with_banned_word
    noun_issues = validate_content(
        fragment_with_banned_word,
        PRODUCTION_FILE_PATH,
        old_content="",
        full_file_content=full_file,
    )
    assert any("canned_results" in each_issue for each_issue in noun_issues)
