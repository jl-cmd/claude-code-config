"""Shared exemption rules for the .md blocker and its post-write companion.

Both `md_to_html_blocker.py` (PreToolUse) and `md_to_html_companion.py`
(PostToolUse) must agree on which file paths bypass the .md → .html policy.
This module is the single source of truth for that decision.
"""

import os
import sys
import tempfile
from pathlib import Path


_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.md_to_html_blocker_constants import (  # noqa: E402
    ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES,
    ALL_EXEMPT_ANYWHERE_FILENAMES,
    ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES,
    ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS,
    ALL_EXEMPT_ROOT_FILENAMES,
    CLAUDE_DEV_ENV_REPO_NAME_SEGMENT,
    CLAUDE_DIRECTORY_NAME,
    MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR,
    PACKAGES_TOP_LEVEL_SEGMENT,
    PLUGIN_ROOT_MARKER_DIRECTORY_NAME,
    REPO_ROOT_MARKER_NAME,
    WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH,
)


def is_exempt_path(file_path: str) -> bool:
    """Return True when the .md file path is exempt from the blocker policy.

    Exemption sources, in order of evaluation:
    - Any segment under `.claude/` or `.claude-plugin/` (case-insensitive)
    - Basename in `ALL_EXEMPT_ANYWHERE_FILENAMES` (e.g. SKILL.md)
    - Anchored under `packages/claude-dev-env/<one of
      ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES>/...` (docs, rules,
      system-prompts source files in this repo)
    - Path segment in `ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS` (agents/skills/commands)
    - Canonical path under a home-relative exempt directory
      (`ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES`)
    - Canonical path under the OS temp directory
    - Ancestor directory contains `.claude-plugin/` (plugin-root marker walk)
    - Basename in `ALL_EXEMPT_ROOT_FILENAMES` and directory is a repo root

    Args:
        file_path: Raw file path from the hook payload. May contain tilde,
            backslashes, or be relative.

    Returns:
        True when the path is exempt, False when the policy applies.
    """
    expanded_path = os.path.expanduser(file_path)
    normalized = os.path.normpath(expanded_path).replace("\\", "/")
    lower_normalized = normalized.lower()
    claude_directory_segment = f"/{CLAUDE_DIRECTORY_NAME}/"
    claude_directory_prefix = f"{CLAUDE_DIRECTORY_NAME}/"
    plugin_directory_segment = f"/{PLUGIN_ROOT_MARKER_DIRECTORY_NAME}/"
    plugin_directory_prefix = f"{PLUGIN_ROOT_MARKER_DIRECTORY_NAME}/"
    if claude_directory_segment in lower_normalized or lower_normalized.startswith(claude_directory_prefix):
        return True
    if plugin_directory_segment in lower_normalized or lower_normalized.startswith(plugin_directory_prefix):
        return True
    basename = os.path.basename(normalized)
    if basename.lower() in ALL_EXEMPT_ANYWHERE_FILENAMES:
        return True
    if _is_under_claude_dev_env_source_subdirectory(file_path, lower_normalized):
        return True
    if _has_plugin_directory_segment(lower_normalized):
        return True
    canonical_normalized_path = os.path.realpath(expanded_path).replace("\\", "/")
    canonical_lower_path = canonical_normalized_path.lower()
    if _is_under_exempt_home_directory(canonical_lower_path):
        return True
    if _is_under_system_temp_directory(canonical_lower_path):
        return True
    if _is_under_plugin_root_marker(canonical_normalized_path):
        return True
    if basename.lower() in ALL_EXEMPT_ROOT_FILENAMES:
        absolute_directory = _resolve_absolute_directory(normalized)
        if _is_repo_root_directory(absolute_directory):
            return True
    return False


def _resolve_absolute_directory(normalized_path: str) -> str:
    directory = os.path.dirname(normalized_path)
    if not directory or directory == ".":
        return os.getcwd()
    if os.path.isabs(directory):
        return directory
    return os.path.abspath(directory)


def _has_plugin_directory_segment(lower_normalized_path: str) -> bool:
    for each_directory_segment in ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS:
        segment_marker = f"/{each_directory_segment}/"
        if segment_marker in lower_normalized_path:
            return True
        if lower_normalized_path.startswith(f"{each_directory_segment}/"):
            return True
    return False


def _looks_like_absolute_path(file_path: str, first_segment: str) -> bool:
    if file_path.startswith("/") or file_path.startswith("\\"):
        return True
    if (
        len(first_segment) == WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH
        and first_segment[1] == ":"
        and first_segment[0].isalpha()
    ):
        return True
    return False


def _is_under_claude_dev_env_source_subdirectory(
    raw_file_path: str, lower_normalized_path: str
) -> bool:
    """Anchored exemption for ``packages/claude-dev-env/<source-dir>/...``.

    The match requires segment-anchored matching at the start of the path
    (relative) or at the root of an absolute path. A nested path like
    ``notes/packages/claude-dev-env/docs/foo.md`` is NOT exempt — only the
    full three-segment anchor matches.

    Args:
        raw_file_path: Original file path as received by the hook (used
            only for absolute-path detection on the first segment).
        lower_normalized_path: Same path lowercased and with separators
            normalized to forward slashes.

    Returns:
        True when the path is anchored under
        ``packages/claude-dev-env/<one of
        ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES>/``.
    """
    all_segments = [
        each_segment
        for each_segment in lower_normalized_path.split("/")
        if each_segment
    ]
    if not all_segments:
        return False
    starting_segment_index_options: list[int] = [0]
    if _looks_like_absolute_path(raw_file_path, all_segments[0]):
        starting_segment_index_options = list(range(len(all_segments)))
    for each_starting_index in starting_segment_index_options:
        if (
            len(all_segments) >= each_starting_index + MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR
            and all_segments[each_starting_index] == PACKAGES_TOP_LEVEL_SEGMENT
            and all_segments[each_starting_index + 1] == CLAUDE_DEV_ENV_REPO_NAME_SEGMENT
            and all_segments[each_starting_index + 2] in ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES
        ):
            return True
    return False


def _is_under_plugin_root_marker(normalized_path: str) -> bool:
    directory = os.path.dirname(normalized_path)
    visited_directories: set[str] = set()
    while directory and directory not in visited_directories:
        visited_directories.add(directory)
        marker_path = os.path.join(directory, PLUGIN_ROOT_MARKER_DIRECTORY_NAME)
        if os.path.isdir(marker_path):
            return True
        parent_directory = os.path.dirname(directory)
        if parent_directory == directory:
            break
        directory = parent_directory
    return False


def _is_under_exempt_home_directory(lower_normalized_path: str) -> bool:
    home_directory = (
        os.path.realpath(os.path.expanduser("~")).replace("\\", "/").rstrip("/").lower()
    )
    if not home_directory:
        return False
    for each_relative_directory in ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES:
        exempt_directory = f"{home_directory}/{each_relative_directory.lower()}"
        if lower_normalized_path.startswith(f"{exempt_directory}/"):
            return True
    return False


def _is_under_system_temp_directory(lower_normalized_path: str) -> bool:
    temp_directory = os.path.realpath(tempfile.gettempdir()).replace("\\", "/").rstrip("/").lower()
    if not temp_directory:
        return False
    return lower_normalized_path.startswith(f"{temp_directory}/")


def _is_repo_root_directory(directory_path: str) -> bool:
    git_marker_path = os.path.join(directory_path, REPO_ROOT_MARKER_NAME)
    return os.path.exists(git_marker_path)
