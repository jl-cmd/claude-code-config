"""Constants shared by grant_project_claude_permissions and revoke_project_claude_permissions."""

from __future__ import annotations

from pathlib import Path


ALL_PERMISSION_ALLOW_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read")

AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE: str = (
    "Trusted local workspace: {project_path}/.claude/** is the user's "
    "project Claude Code config tree; edits inside are routine"
)

CLAUDE_SETTINGS_DIRECTORY_NAME: str = ".claude"

CLAUDE_SETTINGS_FILENAME: str = "settings.json"

TEXT_FILE_ENCODING: str = "utf-8"

UNIQUE_TEMPORARY_SUFFIX_BYTE_LENGTH: int = 8


def get_claude_user_settings_path() -> Path:
    return Path.home() / CLAUDE_SETTINGS_DIRECTORY_NAME / CLAUDE_SETTINGS_FILENAME
