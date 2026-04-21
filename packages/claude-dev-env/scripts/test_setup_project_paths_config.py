"""Regression-guard tests for setup_project_paths_config module constants.

These tests pin values that downstream code depends on. Each test documents
the specific contract the constant carries so future edits that accidentally
break the contract fail fast rather than silently regressing behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

from setup_project_paths_config import (
    ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS,
    JSON_INDENT_SPACES,
)


def test_es_exe_arguments_do_not_include_name_flag() -> None:
    """Pin PR #230 round 3 fix: `-name` makes es.exe emit filenames only.

    The downstream `filter_to_git_roots` function requires full absolute
    paths to extract repo roots. If `-name` is reintroduced, discovery
    silently returns zero results.
    """
    assert "-name" not in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS


def test_json_indent_spaces_equals_two() -> None:
    """Pin the indent contract consumed by json.dumps in setup_project_paths.

    The value is centralized here so the main script body contains no
    literal integer in its json.dumps call.
    """
    assert JSON_INDENT_SPACES == 2
