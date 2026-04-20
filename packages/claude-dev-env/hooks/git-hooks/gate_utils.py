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
    exact_override = _exact_override_gate_path()
    if exact_override is not None:
        return exact_override
    claude_home_directory = _resolved_claude_home_directory()
    return claude_home_directory.joinpath(*GATE_SCRIPT_RELATIVE_PATH)


def is_safe_regular_file(candidate_path: Path) -> bool:
    resolved_candidate = candidate_path.resolve()
    if not _is_candidate_path_allowed(resolved_candidate):
        return False
    try:
        path_stat = os.stat(resolved_candidate)
    except OSError:
        return False
    return stat.S_ISREG(path_stat.st_mode)


def _is_candidate_path_allowed(resolved_candidate: Path) -> bool:
    exact_override = _exact_override_gate_path()
    if exact_override is not None:
        return resolved_candidate == exact_override
    claude_home_directory = _resolved_claude_home_directory()
    return _is_within_directory(resolved_candidate, claude_home_directory)


def _exact_override_gate_path() -> Path | None:
    override_path_raw = os.environ.get(GATE_PATH_OVERRIDE_ENV_VAR, "").strip()
    if not override_path_raw:
        return None
    return Path(override_path_raw).resolve()


def _resolved_claude_home_directory() -> Path:
    claude_home_override = os.environ.get(CLAUDE_HOME_ENV_VAR, "").strip()
    if claude_home_override:
        return Path(claude_home_override).resolve()
    return (Path.home() / CLAUDE_HOME_DEFAULT_SUBDIRECTORY).resolve()


def _is_within_directory(candidate_path: Path, directory: Path) -> bool:
    try:
        candidate_path.relative_to(directory)
        return True
    except ValueError:
        return False
