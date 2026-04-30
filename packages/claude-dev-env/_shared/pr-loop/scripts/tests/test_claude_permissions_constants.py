"""Tests for shared constants powering grant/revoke claude permissions."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = (
        Path(__file__).parent.parent / "config" / "claude_permissions_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "config.claude_permissions_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_exposes_all_permission_allow_tools_tuple() -> None:
    assert constants_module.ALL_PERMISSION_ALLOW_TOOLS == ("Edit", "Write", "Read")


def test_auto_mode_environment_entry_template_is_format_string() -> None:
    rendered_template_text = (
        constants_module.AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE.format(
            project_path="/tmp/x"
        )
    )
    assert "/tmp/x" in rendered_template_text
    assert ".claude/**" in rendered_template_text


def test_get_claude_user_settings_path_ends_in_settings_json() -> None:
    resolved_settings_path = constants_module.get_claude_user_settings_path()
    assert resolved_settings_path.name == constants_module.CLAUDE_SETTINGS_FILENAME
    assert (
        resolved_settings_path.parent.name
        == constants_module.CLAUDE_SETTINGS_DIRECTORY_NAME
    )
