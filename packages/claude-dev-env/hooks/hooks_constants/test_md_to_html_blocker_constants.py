"""Behavior tests for md_to_html_blocker_constants module."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants import md_to_html_blocker_constants as constants_module


def test_claude_code_source_top_directories_enumerates_six_canonical_dirs() -> None:
    """The exempt top-level directory set must match the six canonical Claude
    Code source directories (agents, docs, skills, rules, system-prompts,
    commands). Drift in either direction silently changes the exemption
    surface."""
    expected_directories = frozenset(
        {"agents", "docs", "skills", "rules", "system-prompts", "commands"}
    )
    assert constants_module.ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES == expected_directories
    assert "ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES" in constants_module.__all__


def test_windows_drive_letter_segment_length_is_two() -> None:
    """A Windows drive-letter segment is exactly 'X:' (length 2). The constant
    documents that magic so the absolute-path detector reads as intent rather
    than as an arbitrary numeric literal."""
    assert constants_module.WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH == 2
    assert "WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH" in constants_module.__all__


def test_minimum_segment_count_to_match_indicator_is_four() -> None:
    """Matching `packages/claude-dev-env/<dir>/<file>` requires at least 4
    consecutive path segments from the starting index. The constant documents
    that requirement explicitly."""
    assert constants_module.MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR == 4
    assert "MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR" in constants_module.__all__
