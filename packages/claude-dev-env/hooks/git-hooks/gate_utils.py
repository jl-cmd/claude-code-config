"""Shared utilities for the claude-dev-env git-hook entry points."""

from __future__ import annotations

import os
import stat
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
        return Path(override_path).resolve()
    claude_home_override = os.environ.get(CLAUDE_HOME_ENV_VAR, "").strip()
    if claude_home_override:
        claude_home_directory = Path(claude_home_override).resolve()
    else:
        claude_home_directory = Path.home() / CLAUDE_HOME_DEFAULT_SUBDIRECTORY
    return claude_home_directory.joinpath(*GATE_SCRIPT_RELATIVE_PATH)


def is_safe_regular_file(candidate_path: Path) -> bool:
    allowed_roots = _allowed_gate_script_roots()
    if not any(
        _is_within_directory(candidate_path, each_root)
        for each_root in allowed_roots
    ):
        return False
    try:
        path_stat = os.stat(candidate_path)
    except OSError:
        return False
    return stat.S_ISREG(path_stat.st_mode)


def _allowed_gate_script_roots() -> list[Path]:
    claude_home_override = os.environ.get(CLAUDE_HOME_ENV_VAR, "").strip()
    if claude_home_override:
        claude_home_directory = Path(claude_home_override).resolve()
    else:
        claude_home_directory = (Path.home() / CLAUDE_HOME_DEFAULT_SUBDIRECTORY).resolve()
    override_path_raw = os.environ.get(GATE_PATH_OVERRIDE_ENV_VAR, "").strip()
    allowed = [claude_home_directory]
    if override_path_raw:
        override_resolved = Path(override_path_raw).resolve()
        allowed.append(override_resolved.parent)
    return allowed


def _is_within_directory(candidate_path: Path, directory: Path) -> bool:
    try:
        candidate_path.relative_to(directory)
        return True
    except ValueError:
        return False
