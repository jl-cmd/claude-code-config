"""Configuration constants for claude_permissions_common shared helpers."""

from __future__ import annotations

TEXT_FILE_ENCODING: str = "utf-8"
ALL_PERMISSION_ALLOW_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read")
AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE: str = (
    "Trusted local workspace: Files under {project_path}/.claude/** inherit "
    "the workspace's trust for Edit, Write, Read, and Glob operations EXCEPT "
    "for agent-config files: settings*.json, anything under hooks/, commands/, "
    "agents/, skills/, the mcp.json file, and CLAUDE.md. Edits to those "
    "agent-config files always require explicit per-edit user approval."
)
ATOMIC_WRITE_TEMPORARY_SUFFIX: str = ".tmp"
GIT_DIRECTORY_MARKER: str = ".git"
CLAUDE_DIRECTORY_MARKER: str = ".claude"
CLAUDE_USER_SETTINGS_FILENAME: str = "settings.json"
DEFAULT_SETTINGS_FILE_MODE: int = 0o600
SETTINGS_PERMISSIONS_KEY: str = "permissions"
SETTINGS_ALLOW_KEY: str = "allow"
SETTINGS_ADDITIONAL_DIRECTORIES_KEY: str = "additionalDirectories"
SETTINGS_AUTO_MODE_KEY: str = "autoMode"
SETTINGS_ENVIRONMENT_KEY: str = "environment"
