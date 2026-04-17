#!/usr/bin/env python3
"""
BDD Automate-phase gate (production code touch).

Blocks writes to production source files when no matching test exists
or the matching test has not been modified within the configured
freshness window. Enforces "TDD IS NON-NEGOTIABLE" from CLAUDE.md.
"""
import json
import sys
import time
from pathlib import Path

PRODUCTION_EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx'}
SKIP_PATTERNS = {
    'test_', '_test.', '.test.', 'tests/', '__tests__/',
    'conftest', 'fixture', 'mock', 'stub'
}
SKIP_EXTENSIONS = {'.md', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.txt'}


def _freshness_seconds() -> int:
    return 600


def _bypass_sentinel() -> str:
    return "# pragma: no-tdd-gate"


def _tests_directory_name() -> str:
    return "tests"


def _parent_walk_limit() -> int:
    return 10


def find_nearest_tests_directory(start_directory: Path) -> Path | None:
    current_directory = start_directory
    for _ in range(_parent_walk_limit()):
        sibling_tests = current_directory / _tests_directory_name()
        if sibling_tests.is_dir():
            return sibling_tests
        if current_directory.parent == current_directory:
            return None
        current_directory = current_directory.parent
    return None


def candidate_test_paths_for(production_path: Path) -> list[Path]:
    directory = production_path.parent
    stem = production_path.stem
    extension = production_path.suffix.lower()
    all_candidates: list[Path] = []

    if extension == ".py":
        all_candidates.append(directory / f"test_{stem}.py")
        all_candidates.append(directory / f"{stem}_test.py")
        nearest_tests_directory = find_nearest_tests_directory(directory)
        if nearest_tests_directory is not None:
            all_candidates.append(nearest_tests_directory / f"test_{stem}.py")
        return all_candidates

    if extension in {".tsx", ".ts", ".jsx", ".js"}:
        all_candidates.append(directory / f"{stem}.test{extension}")
        all_candidates.append(directory / f"{stem}.spec{extension}")
        return all_candidates

    return all_candidates


def has_fresh_test(all_candidates: list[Path], freshness_seconds: int) -> bool:
    current_time = time.time()
    for each_candidate in all_candidates:
        if not each_candidate.exists():
            continue
        age_seconds = current_time - each_candidate.stat().st_mtime
        if age_seconds <= freshness_seconds:
            return True
    return False


def build_deny_reason(production_path: Path, all_candidates: list[Path]) -> str:
    candidate_lines = "\n".join(f"  - {each_path}" for each_path in all_candidates)
    return (
        f"[TDD] Blocking write to production file: {production_path}\n"
        f"No matching test file exists, or it has not been modified within the last "
        f"{_freshness_seconds()} seconds.\n"
        f"Expected one of:\n{candidate_lines}\n"
        f"Write a failing test first (RED), then the minimum code to pass it (GREEN).\n"
        f"Bypass (discouraged): include the sentinel '{_bypass_sentinel()}' in the file content."
    )


def emit_allow() -> None:
    allow_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
    print(json.dumps(allow_payload))


def emit_deny(reason: str) -> None:
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(deny_payload))


def _matches_any_skip_pattern(name_lower: str, path_with_forward_slashes: str) -> bool:
    for each_pattern in SKIP_PATTERNS:
        if each_pattern.endswith("/"):
            if each_pattern in path_with_forward_slashes:
                return True
            continue
        if each_pattern in name_lower:
            return True
    return False


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    path = Path(file_path)
    ext = path.suffix.lower()

    # Skip config/docs
    if ext in SKIP_EXTENSIONS:
        sys.exit(0)

    # Skip non-production code files
    if ext not in PRODUCTION_EXTENSIONS:
        sys.exit(0)

    # Skip test files
    name_lower = path.name.lower()
    path_str = str(path).lower().replace("\\", "/")
    if _matches_any_skip_pattern(name_lower, path_str):
        sys.exit(0)

    # Block production code - require confirmation
    written_content = tool_input.get("content", "") or ""
    if _bypass_sentinel() in written_content:
        emit_allow()
        sys.exit(0)

    all_candidates = candidate_test_paths_for(path)
    if has_fresh_test(all_candidates, _freshness_seconds()):
        emit_allow()
        sys.exit(0)

    emit_deny(build_deny_reason(path, all_candidates))
    sys.exit(0)


if __name__ == "__main__":
    main()
