"""Behavior tests for pr_description_enforcer_constants module."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants import pr_description_enforcer_constants as constants_module


def test_plugin_root_is_private_module_attribute() -> None:
    assert hasattr(constants_module, "_PLUGIN_ROOT")
    assert isinstance(constants_module._PLUGIN_ROOT, str)
    assert os.path.isabs(constants_module._PLUGIN_ROOT)


def test_plugin_root_public_name_is_not_exported() -> None:
    assert not hasattr(constants_module, "PLUGIN_ROOT")


def test_pr_guide_path_resolves_under_plugin_root_docs() -> None:
    expected_pr_guide_path = os.path.join(
        constants_module._PLUGIN_ROOT, "docs", "PR_DESCRIPTION_GUIDE.md"
    )
    assert constants_module.PR_GUIDE_PATH == expected_pr_guide_path


def test_minimum_substantive_prose_chars_is_positive_integer() -> None:
    assert isinstance(constants_module.MINIMUM_SUBSTANTIVE_PROSE_CHARS, int)
    assert constants_module.MINIMUM_SUBSTANTIVE_PROSE_CHARS > 0


def test_fenced_code_block_pattern_matches_triple_backtick_block() -> None:
    sample_markdown = "before ```python\ncode\n``` after"
    match = constants_module.FENCED_CODE_BLOCK_PATTERN.search(sample_markdown)
    assert match is not None
    assert match.group(0).startswith("```")
    assert match.group(0).endswith("```")


def test_inline_code_pattern_matches_single_backtick_span() -> None:
    match = constants_module.INLINE_CODE_PATTERN.search("see `value` here")
    assert match is not None
    assert match.group(0) == "`value`"


def test_heading_line_pattern_matches_atx_heading() -> None:
    match = constants_module.HEADING_LINE_PATTERN.search("## Description\n")
    assert match is not None
    assert match.group(0).strip() == "## Description"


def test_bold_pair_pattern_captures_inner_text() -> None:
    match = constants_module.BOLD_PAIR_PATTERN.search("this is **bold** text")
    assert match is not None
    assert match.group(1) == "bold"


def test_bullet_marker_pattern_strips_dash_bullet_from_line() -> None:
    stripped_line = constants_module.BULLET_MARKER_PATTERN.sub("", "- first item")
    assert stripped_line == "first item"


def test_blockquote_marker_pattern_strips_quote_marker_from_line() -> None:
    stripped_line = constants_module.BLOCKQUOTE_MARKER_PATTERN.sub("", "> quoted line")
    assert stripped_line == "quoted line"


def test_link_text_pattern_captures_anchor_text() -> None:
    match = constants_module.LINK_TEXT_PATTERN.search("See [the docs](https://example.com) now")
    assert match is not None
    assert match.group(1) == "the docs"


def test_whitespace_run_pattern_collapses_multiple_spaces() -> None:
    collapsed_text = constants_module.WHITESPACE_RUN_PATTERN.sub(" ", "a   b\t\tc\n\nd")
    assert collapsed_text == "a b c d"


def test_all_heavy_detection_headers_unions_opening_and_testing() -> None:
    assert constants_module.ALL_HEAVY_DETECTION_HEADERS == (
        constants_module.ALL_HEAVY_OPENING_HEADERS
        | constants_module.ALL_HEAVY_TESTING_HEADERS
    )


def test_heavy_detection_header_count_minimum_is_positive_integer() -> None:
    assert isinstance(constants_module.HEAVY_DETECTION_HEADER_COUNT_MIN, int)
    assert constants_module.HEAVY_DETECTION_HEADER_COUNT_MIN >= 1


def test_atomic_write_temp_suffix_starts_with_dot() -> None:
    assert constants_module.ATOMIC_WRITE_TEMP_SUFFIX.startswith(".")
    assert len(constants_module.ATOMIC_WRITE_TEMP_SUFFIX) >= 2


def test_self_closing_reference_message_prefix_and_suffix_compose_full_message() -> None:
    pr_number = 42
    composed_message = (
        f"{constants_module.SELF_CLOSING_REFERENCE_MESSAGE_PREFIX}"
        f"{pr_number}"
        f"{constants_module.SELF_CLOSING_REFERENCE_MESSAGE_SUFFIX}"
    )
    assert "#42" in composed_message
    assert "Fixes/Closes/Resolves" in composed_message
    assert "self-reference" in composed_message


def test_readability_flesch_loosen_factor_is_below_one() -> None:
    assert constants_module.READABILITY_FLESCH_LOOSEN_FACTOR == 0.9
    assert 0.0 < constants_module.READABILITY_FLESCH_LOOSEN_FACTOR < 1.0


def test_readability_sentence_words_loosen_factor_is_above_one() -> None:
    assert constants_module.READABILITY_SENTENCE_WORDS_LOOSEN_FACTOR == 10 / 9
    assert constants_module.READABILITY_SENTENCE_WORDS_LOOSEN_FACTOR > 1.0


def test_loosen_factors_are_inverse_paired() -> None:
    flesch_factor = constants_module.READABILITY_FLESCH_LOOSEN_FACTOR
    sentence_factor = constants_module.READABILITY_SENTENCE_WORDS_LOOSEN_FACTOR
    assert flesch_factor * sentence_factor == pytest.approx(1.0)
