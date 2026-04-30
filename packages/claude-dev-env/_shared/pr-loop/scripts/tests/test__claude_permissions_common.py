"""Tests for shared permission helpers (alias matching the leading-underscore module name)."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType


def _load_common_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "_claude_permissions_common.py"
    parent_directory = str(module_path.parent.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    specification = importlib.util.spec_from_file_location(
        "_claude_permissions_common", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


common = _load_common_module()


def test_text_file_encoding_remains_local_constant_alias() -> None:
    assert common.TEXT_FILE_ENCODING == "utf-8"


def test_text_file_encoding_sourced_from_config() -> None:
    config_module_path = (
        Path(__file__).parent.parent / "config" / "claude_permissions_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "config.claude_permissions_constants", config_module_path
    )
    assert specification is not None
    assert specification.loader is not None
    config_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(config_module)
    assert common.TEXT_FILE_ENCODING == config_module.TEXT_FILE_ENCODING


def test_migrated_constants_no_longer_on_common_module() -> None:
    assert not hasattr(common, "ALL_PERMISSION_ALLOW_TOOLS")
    assert not hasattr(common, "AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE")


def test_path_contains_glob_metacharacters_local_tuple_uses_all_collection_prefix() -> None:
    source_text = inspect.getsource(common.path_contains_glob_metacharacters)
    assert "all_glob_metacharacters_in_path" in source_text
    assert "glob_metacharacters_in_path:" not in source_text.replace(
        "all_glob_metacharacters_in_path", ""
    )
