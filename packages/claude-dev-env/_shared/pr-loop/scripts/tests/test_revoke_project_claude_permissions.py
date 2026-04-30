"""Smoke tests for revoke_project_claude_permissions wiring.

Confirms the module imports cleanly with the constants now sourced from
config/claude_permissions_constants.py and config/claude_settings_keys_constants.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_revoke_module() -> ModuleType:
    scripts_directory = Path(__file__).parent.parent
    parent_directory = str(scripts_directory.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    sys.modules.pop("config", None)
    module_path = scripts_directory / "revoke_project_claude_permissions.py"
    specification = importlib.util.spec_from_file_location(
        "revoke_project_claude_permissions", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_module_imports_constants_from_config_modules() -> None:
    revoke_module = _load_revoke_module()
    assert revoke_module.ALL_PERMISSION_ALLOW_TOOLS == ("Edit", "Write", "Read")
    assert "{project_path}" in revoke_module.AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE
    assert revoke_module.CLAUDE_SETTINGS_PERMISSIONS_KEY == "permissions"
