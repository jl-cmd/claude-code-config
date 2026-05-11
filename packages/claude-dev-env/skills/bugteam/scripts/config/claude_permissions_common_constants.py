"""Configuration constants for claude_permissions_common shared helpers."""

from __future__ import annotations

TEXT_FILE_ENCODING: str = "utf-8"
ALL_PERMISSION_ALLOW_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read")
AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE: str = (
    "Trusted local workspace: {project_path}/.claude/** is the user's "
    "project Claude Code config tree; edits inside are routine"
)
ATOMIC_WRITE_TEMPORARY_SUFFIX: str = ".tmp"
ALL_VALID_PROJECT_ROOT_MARKERS: frozenset[str] = frozenset({".git", ".claude"})
GIT_DIRECTORY_MARKER: str = ".git"
CLAUDE_DIRECTORY_MARKER: str = ".claude"
DEFAULT_SETTINGS_FILE_MODE: int = 0o600
