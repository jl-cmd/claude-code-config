"""Configuration constants for setup_project_paths bootstrap script."""

from __future__ import annotations

ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS = ["-name", "/ad", "folder:.git"]

EXCLUDED_PATH_SEGMENTS = frozenset(
    {
        "temp",
        "tmp",
        "worktree",
        "node_modules",
        ".cache",
        "$recycle.bin",
    }
)

USER_CONFIG_FILE_RELATIVE_PARTS = (".claude", "project-paths.json")

TEMP_FILE_SUFFIX = ".tmp"

ISO_TIMESTAMP_SUFFIX_UTC = "Z"

USER_RESPONSE_AFFIRMATIVE_VALUES = frozenset({"yes", "y"})
