"""Constants shared by grant_project_claude_permissions and revoke_project_claude_permissions."""

from pathlib import Path

from config.preflight_constants import GIT_DIRECTORY_NAME

__all__ = (
    "ALL_PERMISSION_ALLOW_TOOLS",
    "AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE",
    "CLAUDE_SETTINGS_DIRECTORY_NAME",
    "CLAUDE_SETTINGS_FILENAME",
    "GIT_DIRECTORY_NAME",
    "TEXT_FILE_ENCODING",
    "UNIQUE_TEMPORARY_SUFFIX_BYTE_LENGTH",
    "get_claude_user_settings_path",
)


ALL_PERMISSION_ALLOW_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read")

AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE: str = (
    "Trusted local workspace: Files under {project_path}/.claude/** inherit "
    "the workspace's trust for Edit, Write, Read, and Glob operations EXCEPT "
    "for agent-config files: settings*.json, anything under hooks/, commands/, "
    "agents/, skills/, the mcp.json file, and CLAUDE.md. Edits to those "
    "agent-config files always require explicit per-edit user approval."
)

CLAUDE_SETTINGS_DIRECTORY_NAME: str = ".claude"

CLAUDE_SETTINGS_FILENAME: str = "settings.json"

TEXT_FILE_ENCODING: str = "utf-8"

UNIQUE_TEMPORARY_SUFFIX_BYTE_LENGTH: int = 8


def get_claude_user_settings_path() -> Path:
    return Path.home() / CLAUDE_SETTINGS_DIRECTORY_NAME / CLAUDE_SETTINGS_FILENAME
