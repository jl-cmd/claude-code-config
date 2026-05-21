"""Configuration constants for the md_to_html_blocker PreToolUse hook
and its shared exemption helpers (`md_path_exemptions`)."""

from __future__ import annotations


ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES: frozenset[str] = frozenset(
    {"agents", "docs", "skills", "rules", "system-prompts", "commands"}
)

PACKAGES_TOP_LEVEL_SEGMENT: str = "packages"
CLAUDE_DEV_ENV_REPO_NAME_SEGMENT: str = "claude-dev-env"

WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH: int = 2

MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR: int = 4

ALL_EXEMPT_ANYWHERE_FILENAMES: tuple[str, ...] = ("skill.md",)
ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS: tuple[str, ...] = ("agents", "skills", "commands")
ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES: tuple[str, ...] = ("SessionLog",)
ALL_EXEMPT_ROOT_FILENAMES: tuple[str, ...] = ("readme.md", "changelog.md")
REPO_ROOT_MARKER_NAME: str = ".git"
CLAUDE_DIRECTORY_NAME: str = ".claude"
PLUGIN_ROOT_MARKER_DIRECTORY_NAME: str = ".claude-plugin"


__all__ = [
    "ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES",
    "ALL_EXEMPT_ANYWHERE_FILENAMES",
    "ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES",
    "ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS",
    "ALL_EXEMPT_ROOT_FILENAMES",
    "CLAUDE_DEV_ENV_REPO_NAME_SEGMENT",
    "CLAUDE_DIRECTORY_NAME",
    "MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR",
    "PACKAGES_TOP_LEVEL_SEGMENT",
    "PLUGIN_ROOT_MARKER_DIRECTORY_NAME",
    "REPO_ROOT_MARKER_NAME",
    "WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH",
]
