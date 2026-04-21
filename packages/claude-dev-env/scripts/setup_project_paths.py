#!/usr/bin/env python3
"""One-time bootstrap: discover git repos via es.exe and write ~/.claude/project-paths.json.

Invokes Everything's command-line binary (es.exe) with a folders-only query to
locate every ``.git`` directory on fixed drives, applies final-segment and
exclusion filters, presents the discovered mapping to the user, and writes the
approved entries to the per-user config file. Never hardcodes scan roots —
discovery runs against whatever es.exe returns on the local machine.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

GIT_DIRECTORY_SEGMENT_NAME = ".git"
ES_EXE_BINARY_NAME = "es.exe"
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
SUPPORTED_SCHEMA_VERSION = 1
META_KEY = "_meta"
TEMP_FILE_SUFFIX = ".tmp"
UTF8_ENCODING = "utf-8"
ISO_TIMESTAMP_SUFFIX_UTC = "Z"
USER_RESPONSE_AFFIRMATIVE_VALUES = frozenset({"yes", "y"})


class SchemaMismatchError(Exception):
    """Raised when the on-disk config declares a schema newer than this script supports."""


def _split_path_segments(path_string: str) -> list[str]:
    normalized = path_string.replace("\\", "/")
    return [each_segment for each_segment in normalized.split("/") if each_segment]


def _final_segment(path_string: str) -> str:
    all_segments = _split_path_segments(path_string)
    if not all_segments:
        return ""
    return all_segments[-1]


def _parent_of_git_directory(git_directory_path: str) -> str:
    normalized = git_directory_path.replace("\\", "/").rstrip("/")
    last_slash_index = normalized.rfind("/")
    if last_slash_index < 0:
        return ""
    original_separator_kind = "\\" if "\\" in git_directory_path else "/"
    parent_with_forward_slashes = normalized[:last_slash_index]
    if original_separator_kind == "\\":
        return parent_with_forward_slashes.replace("/", "\\")
    return parent_with_forward_slashes


def filter_to_git_roots(all_es_exe_paths: list[str]) -> list[str]:
    """Return repo-root paths for only those entries whose final segment is exactly ``.git``.

    Rejects siblings like ``.gitignore``, ``.github``, ``.gitattributes`` that
    share the ``.git`` prefix but are not the canonical git metadata directory.
    """
    all_repo_roots: list[str] = []
    for each_es_path in all_es_exe_paths:
        if _final_segment(each_es_path).lower() != GIT_DIRECTORY_SEGMENT_NAME:
            continue
        parent_repo_root = _parent_of_git_directory(each_es_path)
        if parent_repo_root:
            all_repo_roots.append(parent_repo_root)
    return all_repo_roots


def apply_exclusion_filter(all_candidate_paths: list[str]) -> list[str]:
    """Drop paths whose any whole segment matches an excluded name (case-insensitive).

    Whole-segment matching preserves legitimate names that merely contain an
    excluded substring (for example ``template`` is retained even though
    ``temp`` is excluded).
    """
    all_retained_paths: list[str] = []
    for each_candidate_path in all_candidate_paths:
        all_lowercased_segments = [
            each_segment.lower()
            for each_segment in _split_path_segments(each_candidate_path)
        ]
        is_excluded = any(
            each_segment in EXCLUDED_PATH_SEGMENTS
            for each_segment in all_lowercased_segments
        )
        if not is_excluded:
            all_retained_paths.append(each_candidate_path)
    return all_retained_paths


def _current_iso_timestamp_utc() -> str:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    formatted = now_utc.strftime("%Y-%m-%dT%H:%M:%S")
    return formatted + ISO_TIMESTAMP_SUFFIX_UTC


def merge_registries(
    existing_registry: dict,
    new_name_by_path: dict[str, str],
) -> dict:
    """Merge newly discovered entries into the existing registry.

    Pre-existing entries not in the new set are preserved. On name collisions
    the newly discovered entry wins. The ``_meta.last_scan`` timestamp is
    refreshed to the current UTC time.
    """
    merged_registry: dict = {
        each_key: each_value
        for each_key, each_value in existing_registry.items()
        if each_key != META_KEY
    }
    for each_name, each_path in new_name_by_path.items():
        merged_registry[each_name] = each_path
    merged_registry[META_KEY] = {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "last_scan": _current_iso_timestamp_utc(),
    }
    return merged_registry


def _read_existing_registry(target_file: Path) -> dict:
    if not target_file.is_file():
        return {}
    try:
        raw_text = target_file.read_text(encoding=UTF8_ENCODING)
    except OSError:
        return {}
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _verify_schema_version_is_supported(existing_registry: dict) -> None:
    existing_meta = existing_registry.get(META_KEY)
    if not isinstance(existing_meta, dict):
        return
    existing_schema_version = existing_meta.get("schema_version")
    if not isinstance(existing_schema_version, int):
        return
    if existing_schema_version > SUPPORTED_SCHEMA_VERSION:
        raise SchemaMismatchError(
            f"On-disk schema_version {existing_schema_version} exceeds supported "
            f"version {SUPPORTED_SCHEMA_VERSION}; refusing to overwrite."
        )


def write_registry_atomically(registry_to_write: dict, target_file: Path) -> None:
    """Serialize registry to a temp sibling and rename into place atomically.

    Refuses to overwrite a file whose on-disk ``schema_version`` is newer than
    the version this script understands.
    """
    existing_registry = _read_existing_registry(target_file)
    _verify_schema_version_is_supported(existing_registry)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    temp_sibling_path = target_file.with_suffix(target_file.suffix + TEMP_FILE_SUFFIX)
    serialized_text = json.dumps(registry_to_write, indent=2, sort_keys=True)
    try:
        temp_sibling_path.write_text(serialized_text, encoding=UTF8_ENCODING)
        os.replace(temp_sibling_path, target_file)
    finally:
        if temp_sibling_path.exists():
            try:
                temp_sibling_path.unlink()
            except OSError:
                pass


def _everything_binary_is_available() -> bool:
    return shutil.which(ES_EXE_BINARY_NAME) is not None


def _run_es_exe_folders_query() -> list[str]:
    completion = subprocess.run(
        [ES_EXE_BINARY_NAME, *ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS],
        capture_output=True,
        text=True,
        check=False,
    )
    if completion.returncode != 0:
        return []
    return [line.strip() for line in completion.stdout.splitlines() if line.strip()]


def _deduplicate_preserving_order(all_paths: list[str]) -> list[str]:
    seen_normalized: set[str] = set()
    all_unique_paths: list[str] = []
    for each_path in all_paths:
        normalized_key = os.path.normpath(each_path).lower()
        if normalized_key in seen_normalized:
            continue
        seen_normalized.add(normalized_key)
        all_unique_paths.append(each_path)
    return all_unique_paths


def discover_repo_roots_via_everything() -> list[str]:
    """Run es.exe, filter to genuine git roots, and deduplicate."""
    all_raw_paths = _run_es_exe_folders_query()
    all_git_roots = filter_to_git_roots(all_raw_paths)
    all_included = apply_exclusion_filter(all_git_roots)
    return _deduplicate_preserving_order(sorted(all_included))


def _default_user_config_path() -> Path:
    dot_claude_segment, file_name_segment = USER_CONFIG_FILE_RELATIVE_PARTS
    return Path.home() / dot_claude_segment / file_name_segment


def _prompt_for_affirmative(prompt_text: str) -> bool:
    user_response = input(prompt_text).strip().lower()
    return user_response in USER_RESPONSE_AFFIRMATIVE_VALUES


def _leaf_name_of(repo_root_path: str) -> str:
    leaf = _final_segment(repo_root_path)
    return leaf if leaf else repo_root_path


def prompt_and_write(
    name_by_path: dict[str, str],
    save_path: Path,
) -> None:
    """Present the mapping to the user and write it only on explicit approval.

    The mapping's keys are repo names and the values are absolute paths. The
    function prints a preview and asks for confirmation; declining writes
    nothing.
    """
    print(f"Proposed mapping (save target: {save_path}):")
    for each_name, each_path in sorted(name_by_path.items()):
        print(f"  {each_name} -> {each_path}")
    print()
    if not _prompt_for_affirmative("Write this mapping to the config file? (yes/no): "):
        print("Aborted. Nothing written.")
        return
    existing_registry = _read_existing_registry(save_path)
    merged = merge_registries(existing_registry, name_by_path)
    write_registry_atomically(merged, save_path)
    print(f"Wrote {len(name_by_path)} entries to {save_path}.")


def _build_name_by_path_from_roots(all_repo_roots: list[str]) -> dict[str, str]:
    name_by_path: dict[str, str] = {}
    for each_repo_root in all_repo_roots:
        each_leaf_name = _leaf_name_of(each_repo_root)
        if each_leaf_name in name_by_path:
            continue
        name_by_path[each_leaf_name] = each_repo_root
    return name_by_path


def main() -> int:
    if not _everything_binary_is_available():
        print(
            f"ERROR: {ES_EXE_BINARY_NAME} not found on PATH. Install Everything "
            "and ensure its command-line binary is available before running this script.",
            file=sys.stderr,
        )
        return 1
    print(
        f"Running Everything folder scan for {GIT_DIRECTORY_SEGMENT_NAME} directories..."
    )
    all_repo_roots = discover_repo_roots_via_everything()
    if not all_repo_roots:
        print("No candidate git repositories found via es.exe.")
        return 0
    print(f"Found {len(all_repo_roots)} candidate repositories.")
    name_by_path = _build_name_by_path_from_roots(all_repo_roots)
    save_path = _default_user_config_path()
    prompt_and_write(name_by_path=name_by_path, save_path=save_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
