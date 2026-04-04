#!/usr/bin/env python3
"""
Validate E2E test consistency between online/offline specs.

Two checks:
1. Naming: offline tests must mirror online test names with " offline" suffix.
2. Coverage: when a new online e2e test file is written, a corresponding
   offline equivalent must exist. Blocks if missing.

Triggered as PostToolUse hook when editing spec files.
"""

import json
import os
import re
import sys
from pathlib import Path


E2E_TEST_DIRECTORY = "frontend/tests/e2e"


def extract_test_names(file_path: Path) -> set[str]:
    """Extract test names from spec file."""
    content = file_path.read_text()
    pattern = r"test\(['\"]([^'\"]+)['\"]"
    return set(re.findall(pattern, content))


def validate_e2e_naming(project_root: Path) -> list[str]:
    """Return list of naming violations.

    Only validates tests that follow the naming convention (end with " offline").
    Legacy tests without the suffix are ignored - they may intentionally differ.
    """
    online = project_root / E2E_TEST_DIRECTORY / "online.spec.ts"
    offline = project_root / E2E_TEST_DIRECTORY / "offline.spec.ts"

    if not online.exists() or not offline.exists():
        return []

    online_tests = extract_test_names(online)
    offline_tests = extract_test_names(offline)

    violations = []

    for test in offline_tests:
        if not test.endswith(" offline"):
            continue

        online_name = test.removesuffix(" offline")
        if online_name not in online_tests:
            violations.append(f"No online pair for: '{test}'")

    return violations


def validate_offline_coverage(file_path: str, project_root: Path) -> list[str]:
    """Check that online e2e test files have a corresponding offline file.

    When a new online spec file is written, the offline equivalent must exist.
    Returns blocking violations if offline file is missing.
    """
    e2e_directory = project_root / E2E_TEST_DIRECTORY
    file_name = Path(file_path).name

    if "offline" in file_name:
        return []

    if not file_name.endswith(".spec.ts"):
        return []

    offline_name = file_name.replace(".spec.ts", ".offline.spec.ts")
    if file_name == "online.spec.ts":
        offline_name = "offline.spec.ts"

    offline_path = e2e_directory / offline_name
    if not offline_path.exists():
        return [f"Missing offline equivalent: {offline_name} required for {file_name}"]

    return []


def main() -> None:
    """Hook entry point - reads tool input from stdin."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    if ".spec.ts" not in file_path:
        sys.exit(0)

    path_object = Path(file_path)
    project_root = path_object.parent
    while project_root != project_root.parent:
        if (project_root / E2E_TEST_DIRECTORY).exists():
            break
        project_root = project_root.parent
    else:
        sys.exit(0)

    if not (project_root / E2E_TEST_DIRECTORY).exists():
        sys.exit(0)

    naming_violations = validate_e2e_naming(project_root)
    coverage_violations = validate_offline_coverage(file_path, project_root)

    if coverage_violations:
        violation_list = "; ".join(coverage_violations)
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"[E2E COVERAGE] Offline test required: {violation_list}"
            }
        }
        print(json.dumps(result))
        sys.stdout.flush()
        sys.exit(0)

    if naming_violations:
        violation_list = "; ".join(naming_violations)
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"[E2E NAMING] {violation_list}. Offline tests must mirror online names with ' offline' suffix."
            }
        }
        print(json.dumps(result))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()
