"""Tests for _shared permission helpers extracted from skills/bugteam/scripts/."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_common_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "_claude_permissions_common.py"
    parent_directory = str(module_path.parent.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    spec = importlib.util.spec_from_file_location(
        "_claude_permissions_common", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _load_common_module()


def test_return_normalized_path_when_cwd_contains_spaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory_with_spaces = tmp_path / "dir with spaces"
    directory_with_spaces.mkdir()
    monkeypatch.chdir(directory_with_spaces)
    returned_project_path = common.get_current_project_path()
    expected_suffix = "/dir with spaces"
    assert returned_project_path.endswith(expected_suffix)
    assert "\\" not in returned_project_path
    built_rule = common.build_permission_rule("Edit", returned_project_path)
    assert built_rule.startswith("Edit(")
    assert built_rule.endswith("/.claude/**)")
    assert "dir with spaces" in built_rule


def test_raise_when_cwd_contains_glob_metacharacters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory_with_star = tmp_path / "weird[dir]"
    directory_with_star.mkdir()
    monkeypatch.chdir(directory_with_star)
    with pytest.raises(ValueError, match="glob metacharacters"):
        common.get_current_project_path()


def test_flag_glob_metacharacters_in_any_position() -> None:
    assert common.path_contains_glob_metacharacters("/home/user/[dir]/project")
    assert common.path_contains_glob_metacharacters("/home/user/project*")
    assert not common.path_contains_glob_metacharacters("/home/user/dir with spaces")


def test_text_file_encoding_remains_local_constant() -> None:
    assert common.TEXT_FILE_ENCODING == "utf-8"


def test_module_no_longer_redeclares_migrated_constants() -> None:
    assert not hasattr(common, "ALL_PERMISSION_ALLOW_TOOLS")
    assert not hasattr(common, "AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE")
