"""Behavior tests for query-name pattern and exit-code routing contracts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from config.hook_log_extractor_constants import (
    EXIT_CODE_ENVIRONMENT_MISSING,
    EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING,
    EXIT_CODE_SUCCESS,
    EXIT_CODE_UNKNOWN_QUERY,
    QUERY_NAME_PATTERN,
    SENTINEL_INSERT_FAILURE_MESSAGE,
    SENTINEL_SELECT_FAILURE_MESSAGE,
)


def _matches_query_pattern(candidate_name: str) -> bool:
    return re.fullmatch(QUERY_NAME_PATTERN, candidate_name) is not None


def test_query_name_pattern_allows_canonical_pre_baked_query_name() -> None:
    assert _matches_query_pattern("top_blockers_last_24_hours")


def test_query_name_pattern_rejects_path_traversal() -> None:
    assert not _matches_query_pattern("../etc/passwd")


def test_query_name_pattern_rejects_uppercase() -> None:
    assert not _matches_query_pattern("TopBlockers")


def test_query_name_pattern_rejects_hyphens() -> None:
    assert not _matches_query_pattern("top-blockers")


def test_query_name_pattern_rejects_empty_string() -> None:
    assert not _matches_query_pattern("")


def test_unknown_query_exit_code_distinguishes_from_success() -> None:
    assert EXIT_CODE_UNKNOWN_QUERY != EXIT_CODE_SUCCESS


def test_unknown_query_exit_code_distinguishes_from_extractor_offline_fallback() -> None:
    assert EXIT_CODE_UNKNOWN_QUERY != EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING


def test_unknown_query_exit_code_distinguishes_from_init_environment_missing() -> None:
    assert EXIT_CODE_UNKNOWN_QUERY != EXIT_CODE_ENVIRONMENT_MISSING


def test_extractor_offline_fallback_matches_success_so_stop_hook_does_not_surface_failure() -> None:
    assert EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING == EXIT_CODE_SUCCESS


def test_sentinel_insert_failure_message_is_distinct_from_select_failure() -> None:
    assert SENTINEL_INSERT_FAILURE_MESSAGE != SENTINEL_SELECT_FAILURE_MESSAGE
    assert SENTINEL_INSERT_FAILURE_MESSAGE
