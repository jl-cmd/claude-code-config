"""Shared helpers for grant_project_claude_permissions and revoke_project_claude_permissions."""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn


TEXT_FILE_ENCODING: str = "utf-8"
GLOB_METACHARACTERS_IN_PATH: tuple[str, ...] = (
    "*",
    "?",
    "[",
    "]",
    "(",
    ")",
    "{",
    "}",
    ",",
)

JSON_INDENT_SPACES: int = 2
PERMISSION_ALLOW_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read")


AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE: str = (
    "Trusted local workspace: {project_path}/.claude/** is the user's "
    "project Claude Code config tree; edits inside are routine"
)


def exit_with_error(message: str) -> NoReturn:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def path_contains_glob_metacharacters(candidate_path: str) -> bool:
    return any(
        each_character in candidate_path
        for each_character in GLOB_METACHARACTERS_IN_PATH
    )


def path_contains_whitespace(candidate_path: str) -> bool:
    return any(each_character.isspace() for each_character in candidate_path)


def get_current_project_path() -> str:
    normalized_project_path = str(Path.cwd()).replace("\\", "/")
    if path_contains_glob_metacharacters(normalized_project_path):
        raise ValueError(
            f"Current directory path contains glob metacharacters and cannot "
            f"be used to build permission rules safely: {normalized_project_path}"
        )
    if path_contains_whitespace(normalized_project_path):
        raise ValueError(
            f"Current directory path contains whitespace and cannot be used "
            f"to build permission rules safely: {normalized_project_path}"
        )
    return normalized_project_path


def build_permission_rule(tool_name: str, project_path: str) -> str:
    return f"{tool_name}({project_path}/.claude/**)"


def build_permission_rules(
    project_path: str, permission_allow_tools: tuple[str, ...]
) -> list[str]:
    return [
        build_permission_rule(each_tool, project_path)
        for each_tool in permission_allow_tools
    ]


def load_settings(settings_path: Path) -> dict[str, Any]:
    if not settings_path.exists():
        return {}
    parsed_settings: dict[str, Any] = {}
    try:
        parsed_settings = json.loads(
            settings_path.read_text(encoding=TEXT_FILE_ENCODING)
        )
    except json.JSONDecodeError as decode_error:
        exit_with_error(
            f"Refusing to modify {settings_path}: existing file is not valid JSON "
            f"({decode_error}). Fix or back up the file manually, then re-run."
        )
    if not isinstance(parsed_settings, dict):
        exit_with_error(
            f"Refusing to modify {settings_path}: existing file's root is "
            f"{type(parsed_settings).__name__}, not a JSON object. Fix or back up "
            f"the file manually, then re-run."
        )
    return parsed_settings


def save_settings(settings_path: Path, settings: dict[str, Any]) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_settings = json.dumps(settings, indent=JSON_INDENT_SPACES)
    temporary_file_descriptor, temporary_file_path = tempfile.mkstemp(
        prefix=settings_path.name, dir=str(settings_path.parent)
    )
    try:
        with os.fdopen(
            temporary_file_descriptor, "w", encoding=TEXT_FILE_ENCODING
        ) as temporary_file:
            temporary_file.write(serialized_settings)
        os.replace(temporary_file_path, settings_path)
    except OSError as io_error:
        try:
            if os.path.exists(temporary_file_path):
                os.unlink(temporary_file_path)
        except OSError:
            pass
        exit_with_error(f"Failed to save settings to {settings_path}: {io_error}")


def append_if_missing(target_list: list[str], new_value: str) -> bool:
    if new_value in target_list:
        return False
    target_list.append(new_value)
    return True


def ensure_dict_section(settings: dict[str, Any], section_name: str) -> dict[str, Any]:
    """Return an existing dict section or create an empty one if absent.

    A missing key and an explicit JSON null are treated identically: both
    produce a fresh empty dict stored back into settings. Any other non-dict
    value (string, list, number, bool) calls exit_with_error to avoid
    overwriting user data.
    """
    existing_section = settings.get(section_name)
    if existing_section is None:
        replacement_section: dict[str, Any] = {}
        settings[section_name] = replacement_section
        return replacement_section
    if not isinstance(existing_section, dict):
        exit_with_error(
            f"Refusing to modify settings key {section_name!r}: existing value "
            f"is {type(existing_section).__name__}, not a JSON object. Fix or "
            f"remove the key manually, then re-run."
        )
    return existing_section


def ensure_list_entry(section: dict[str, Any], entry_name: str) -> list[Any]:
    """Return an existing list entry or create an empty one if absent.

    A missing key and an explicit JSON null are treated identically: both
    produce a fresh empty list stored back into the section. Any other
    non-list value (string, dict, number, bool) calls exit_with_error to
    avoid overwriting user data.
    """
    existing_entry = section.get(entry_name)
    if existing_entry is None:
        replacement_entry: list[Any] = []
        section[entry_name] = replacement_entry
        return replacement_entry
    if not isinstance(existing_entry, list):
        exit_with_error(
            f"Refusing to modify settings entry {entry_name!r}: existing value "
            f"is {type(existing_entry).__name__}, not a JSON array. Fix or "
            f"remove the entry manually, then re-run."
        )
    return existing_entry
