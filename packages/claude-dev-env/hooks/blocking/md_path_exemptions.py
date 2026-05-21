"""Shared exemption rules for the .md blocker and its post-write companion.

Both `md_to_html_blocker.py` (PreToolUse) and `md_to_html_companion.py`
(PostToolUse) must agree on which file paths bypass the .md → .html policy.
This module is the single source of truth for that decision.
"""

import os
import sys
import tempfile
from pathlib import Path


for each_cached_module_name in [
    each_module_key
    for each_module_key in list(sys.modules)
    if each_module_key == "config" or each_module_key.startswith("config.")
]:
    sys.modules.pop(each_cached_module_name, None)
_blocking_directory = str(Path(__file__).resolve().parent)
while _blocking_directory in sys.path:
    sys.path.remove(_blocking_directory)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)

from config.md_blocker_constants import (  # noqa: E402
    ALL_EXEMPT_ANYWHERE_FILENAMES,
    ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES,
    ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS,
    ALL_EXEMPT_ROOT_FILENAMES,
    CLAUDE_DIRECTORY_NAME,
    PLUGIN_ROOT_MARKER_DIRECTORY_NAME,
    REPO_ROOT_MARKER_NAME,
)


def is_exempt_path(file_path: str) -> bool:
    """Return True when the .md file path is exempt from the blocker policy.

    Exemption sources, in order of evaluation:
    - Any segment under `.claude/` or `.claude-plugin/` (case-insensitive)
    - Basename in `ALL_EXEMPT_ANYWHERE_FILENAMES` (e.g. SKILL.md)
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
