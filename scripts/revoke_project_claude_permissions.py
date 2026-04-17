"""Revoke the permissions previously granted by grant_project_claude_permissions.

Run from the same project root you previously granted. Removes the matching
allow rules, the additionalDirectories entry, and the autoMode environment
entry from ~/.claude/settings.json. Safe to run when no prior grant exists.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


CLAUDE_USER_SETTINGS_PATH: Path = Path.home() / ".claude" / "settings.json"
PERMISSION_ALLOW_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read")
AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE: str = (
    "Trusted local workspace: {project_path}/.claude/** is the user's "
    "project Claude Code config tree; edits inside are routine"
)
JSON_INDENT_SPACES: int = 2
TEXT_FILE_ENCODING: str = "utf-8"
GLOB_METACHARACTERS_IN_PATH: tuple[str, ...] = ("*", "?", "[", "]", "(", ")")


def path_contains_glob_metacharacters(candidate_path: str) -> bool:
    return any(
        each_character in candidate_path
        for each_character in GLOB_METACHARACTERS_IN_PATH
    )


def get_current_project_path() -> str:
    normalized_project_path = str(Path.cwd()).replace("\\", "/")
    if path_contains_glob_metacharacters(normalized_project_path):
        raise ValueError(
            f"Current directory path contains glob metacharacters and cannot "
            f"be used to build permission rules safely: {normalized_project_path}"
        )
    return normalized_project_path


def build_permission_rule(tool_name: str, project_path: str) -> str:
    return f"{tool_name}({project_path}/.claude/**)"


def build_permission_rules(project_path: str) -> list[str]:
    return [
        build_permission_rule(each_tool, project_path)
        for each_tool in PERMISSION_ALLOW_TOOLS
    ]


def load_settings(settings_path: Path) -> dict[str, Any]:
    if not settings_path.exists():
        return {}
    try:
        parsed_settings = json.loads(settings_path.read_text(encoding=TEXT_FILE_ENCODING))
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed_settings, dict):
        return {}
    return parsed_settings


def save_settings(settings_path: Path, settings: dict[str, Any]) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_settings = json.dumps(settings, indent=JSON_INDENT_SPACES)
    temporary_file_descriptor, temporary_file_path = tempfile.mkstemp(
        prefix=settings_path.name, dir=str(settings_path.parent)
    )
    try:
        with os.fdopen(temporary_file_descriptor, "w", encoding=TEXT_FILE_ENCODING) as temporary_file:
            temporary_file.write(serialized_settings)
        os.replace(temporary_file_path, settings_path)
    except BaseException:
        if os.path.exists(temporary_file_path):
            os.unlink(temporary_file_path)
        raise


def remove_values_from_list(target_list: list[str], values_to_remove: set[str]) -> int:
    original_length = len(target_list)
    target_list[:] = [
        each_value for each_value in target_list if each_value not in values_to_remove
    ]
    return original_length - len(target_list)


def remove_rules_from_allow_list(
    settings: dict[str, Any], rules_to_remove: list[str]
) -> int:
    permissions_section = settings.get("permissions")
    if not isinstance(permissions_section, dict):
        return 0
    existing_allow_list = permissions_section.get("allow")
    if not isinstance(existing_allow_list, list):
        return 0
    return remove_values_from_list(existing_allow_list, set(rules_to_remove))


def remove_directory_from_additional_directories(
    settings: dict[str, Any], directory_path: str
) -> int:
    permissions_section = settings.get("permissions")
    if not isinstance(permissions_section, dict):
        return 0
    existing_directories = permissions_section.get("additionalDirectories")
    if not isinstance(existing_directories, list):
        return 0
    return remove_values_from_list(existing_directories, {directory_path})


def remove_auto_mode_environment_entry(
    settings: dict[str, Any], entry_text: str
) -> int:
    auto_mode_section = settings.get("autoMode")
    if not isinstance(auto_mode_section, dict):
        return 0
    existing_environment = auto_mode_section.get("environment")
    if not isinstance(existing_environment, list):
        return 0
    return remove_values_from_list(existing_environment, {entry_text})


def revoke_permissions_for_current_directory() -> None:
    project_path = get_current_project_path()
    permission_rules = build_permission_rules(project_path)
    environment_entry = AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE.format(
        project_path=project_path
    )
    if not CLAUDE_USER_SETTINGS_PATH.exists():
        print(f"Project path: {project_path}")
        print(f"Settings file: {CLAUDE_USER_SETTINGS_PATH}")
        print("No settings file found; nothing to revoke.")
        return
    settings = load_settings(CLAUDE_USER_SETTINGS_PATH)
    rules_removed_count = remove_rules_from_allow_list(settings, permission_rules)
    directories_removed_count = remove_directory_from_additional_directories(
        settings, project_path
    )
    environment_entries_removed_count = remove_auto_mode_environment_entry(
        settings, environment_entry
    )
    save_settings(CLAUDE_USER_SETTINGS_PATH, settings)
    print(f"Project path: {project_path}")
    print(f"Settings file: {CLAUDE_USER_SETTINGS_PATH}")
    print(f"Allow rules removed: {rules_removed_count} of {len(permission_rules)}")
    print(f"Additional directories removed: {directories_removed_count}")
    print(f"Auto-mode environment entries removed: {environment_entries_removed_count}")


if __name__ == "__main__":
    revoke_permissions_for_current_directory()
