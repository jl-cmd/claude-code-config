"""Shared utilities for the claude-dev-env git-hook entry points."""

from __future__ import annotations

import os
from pathlib import Path

from config import (
    CLAUDE_HOME_DEFAULT_SUBDIRECTORY,
    CLAUDE_HOME_ENV_VAR,
    GATE_PATH_OVERRIDE_ENV_VAR,
    GATE_SCRIPT_RELATIVE_PATH,
)


def resolve_gate_script_path() -> Path:
    override_path = os.environ.get(GATE_PATH_OVERRIDE_ENV_VAR, "").strip()
    if override_path:
        return Path(override_path)
    claude_home_override = os.environ.get(CLAUDE_HOME_ENV_VAR, "").strip()
    if claude_home_override:
        claude_home_directory = Path(claude_home_override)
    else:
        claude_home_directory = Path.home() / CLAUDE_HOME_DEFAULT_SUBDIRECTORY
    return claude_home_directory.joinpath(*GATE_SCRIPT_RELATIVE_PATH)
