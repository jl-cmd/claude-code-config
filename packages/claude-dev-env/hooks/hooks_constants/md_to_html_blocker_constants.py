"""Configuration constants for the md_to_html_blocker PreToolUse hook."""

from __future__ import annotations


ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES: frozenset[str] = frozenset(
    {"agents", "docs", "skills", "rules", "system-prompts", "commands"}
)

WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH: int = 2

MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR: int = 4


__all__ = [
    "ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES",
    "MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR",
    "WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH",
]
