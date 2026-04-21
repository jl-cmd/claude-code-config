"""Regression-guard tests for setup_project_paths_constants module."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hook_config.setup_project_paths_constants import (
    ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS,
)


def test_es_exe_arguments_is_immutable_tuple() -> None:
    """Pin PR #230 round 6: constant must be a tuple, not a mutable list.

    Tuples unpack identically into subprocess.run([...]) args and prevent
    accidental mutation of the shared constant at call sites.
    """
    assert isinstance(ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS, tuple)


def test_es_exe_arguments_contains_folders_only_flag() -> None:
    assert "/ad" in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS


def test_es_exe_arguments_contains_git_folder_query() -> None:
    assert "folder:.git" in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS


def test_es_exe_arguments_do_not_include_name_flag() -> None:
    assert "-name" not in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS
