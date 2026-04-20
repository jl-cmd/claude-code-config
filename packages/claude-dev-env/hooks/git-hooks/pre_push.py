#!/usr/bin/env python3
"""Git pre-push hook: run the CODE_RULES gate over commits about to be pushed.

Installed to the user's shared git-hooks directory via the claude-dev-env
installer; git invokes this file as `pre-push` (the installer strips the
`_` and `.py` suffix when copying into the live hooks path).

Protocol: git pre-push provides remote name and URL as argv, then writes
`<local-ref> <local-sha> <remote-ref> <remote-sha>` lines on stdin. The
first non-zero remote-sha is used as the gate `--base`, so violations are
scoped to commits that are not already on the remote. When every remote
object name is zero (new branch) or stdin is empty, the gate falls back
to the remote's default branch symbolic ref.

Exit codes:
  0 - commits to be pushed pass the gate (or the gate is not installed).
  1 - one or more commits introduce blocking violations.
  2 - unexpected invocation failure (e.g., subprocess could not launch).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BASE_REFERENCE_ARGUMENT: str = "--base"
DEFAULT_REMOTE_BASE_REFERENCE: str = "origin/HEAD"
ALL_ZEROS_OBJECT_NAME_CHARACTER: str = "0"
STDIN_LINE_FIELD_COUNT: int = 4
STDIN_REMOTE_OBJECT_FIELD_INDEX: int = 3
GATE_PATH_OVERRIDE_ENV_VAR: str = "CODE_RULES_GATE_PATH"
CLAUDE_HOME_ENV_VAR: str = "CLAUDE_HOME"
CLAUDE_HOME_DEFAULT_SUBDIRECTORY: str = ".claude"
GATE_SCRIPT_RELATIVE_PATH: tuple[str, ...] = (
    "skills",
    "bugteam",
    "scripts",
    "bugteam_code_rules_gate.py",
)


def resolve_gate_script_path() -> Path:
    override_path = os.environ.get(GATE_PATH_OVERRIDE_ENV_VAR, "").strip()
    if override_path:
        return Path(override_path)
    claude_home_override = os.environ.get(CLAUDE_HOME_ENV_VAR, "").strip()
    if claude_home_override:
        claude_home_directory = Path(claude_home_override)
    else:
        claude_home_directory = Path.home() / CLAUDE_HOME_DEFAULT_SUBDIRECTORY
    return claude_home_directory.joinpath(*GATE_SCRIPT_RELATIVE_PATH)


def is_all_zeros_object_name(object_name: str) -> bool:
    stripped_object_name = object_name.strip()
    if not stripped_object_name:
        return True
    return all(
        each_character == ALL_ZEROS_OBJECT_NAME_CHARACTER
        for each_character in stripped_object_name
    )


def resolve_base_reference_from_stdin(stdin_text: str) -> str:
    for each_line in stdin_text.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        fields = stripped_line.split()
        if len(fields) < STDIN_LINE_FIELD_COUNT:
            continue
        remote_object_name = fields[STDIN_REMOTE_OBJECT_FIELD_INDEX]
        if not is_all_zeros_object_name(remote_object_name):
            return remote_object_name
    return DEFAULT_REMOTE_BASE_REFERENCE


def invoke_gate(gate_script_path: Path, base_reference: str) -> int:
    completion = subprocess.run(
        [
            sys.executable,
            str(gate_script_path),
            BASE_REFERENCE_ARGUMENT,
            base_reference,
        ],
        check=False,
    )
    return completion.returncode


def main() -> int:
    gate_script_path = resolve_gate_script_path()
    if not gate_script_path.is_file():
        return 0
    base_reference = resolve_base_reference_from_stdin(sys.stdin.read())
    return invoke_gate(gate_script_path, base_reference)


if __name__ == "__main__":
    sys.exit(main())
