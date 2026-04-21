"""Load the per-user project-path registry from ~/.claude/project-paths.json."""

import json
import os
import sys
from pathlib import Path

_META_KEY = "_meta"
_DEFAULT_CONFIG_RELATIVE_PARTS = (".claude", "project-paths.json")
_SCHEMA_VERSION = 1


def _default_config_path() -> Path:
    dot_claude_segment, file_name_segment = _DEFAULT_CONFIG_RELATIVE_PARTS
    return Path.home() / dot_claude_segment / file_name_segment


def _normalize_path_separators(raw_path: str) -> str:
    return os.path.normpath(raw_path)


def load_registry(config_path: Path | None = None) -> dict[str, str]:
    """Return the name-to-absolute-path mapping with the _meta key stripped.

    Returns an empty dict when the file is missing, unreadable, or malformed.
    Logs one line to stderr on any unexpected error.
    """
    resolved_path = config_path if config_path is not None else _default_config_path()
    if not resolved_path.is_file():
        return {}
    try:
        raw_text = resolved_path.read_text(encoding="utf-8")
    except OSError as e:
        print(
            f"project_paths_reader: cannot read {resolved_path}: {e}", file=sys.stderr
        )
        return {}
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(
            f"project_paths_reader: malformed JSON in {resolved_path}: {e}",
            file=sys.stderr,
        )
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        key: value
        for key, value in parsed.items()
        if key != _META_KEY and isinstance(key, str) and isinstance(value, str)
    }


def registry_contains_path(known_registry: dict[str, str], path_to_find: str) -> bool:
    """Return True when the given path appears as any registry value.

    Normalizes both sides before comparing so Windows and POSIX separator
    forms of the same path compare equal.
    """
    normalized_target = _normalize_path_separators(path_to_find)
    for each_registered_path in known_registry.values():
        if _normalize_path_separators(each_registered_path) == normalized_target:
            return True
    return False
