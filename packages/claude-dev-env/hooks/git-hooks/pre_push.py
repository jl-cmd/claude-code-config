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

from config import (
    ALL_ZEROS_OBJECT_NAME_CHARACTER,
    BASE_REFERENCE_ARGUMENT,
    CLAUDE_HOME_DEFAULT_SUBDIRECTORY,
    CLAUDE_HOME_ENV_VAR,
    DEFAULT_REMOTE_BASE_REFERENCE,
    GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE,
    GATE_PATH_OVERRIDE_ENV_VAR,
    GATE_SCRIPT_RELATIVE_PATH,
    STDIN_LINE_FIELD_COUNT,
    STDIN_REMOTE_OBJECT_FIELD_INDEX,
)


def resolve_gate_script_path() -> Path:
    gate_path_override_env_var = GATE_PATH_OVERRIDE_ENV_VAR
    claude_home_env_var = CLAUDE_HOME_ENV_VAR
    claude_home_default_subdirectory = CLAUDE_HOME_DEFAULT_SUBDIRECTORY
    gate_script_relative_path = GATE_SCRIPT_RELATIVE_PATH
    override_path = os.environ.get(gate_path_override_env_var, "").strip()
    if override_path:
        return Path(override_path)
    claude_home_override = os.environ.get(claude_home_env_var, "").strip()
    if claude_home_override:
        claude_home_directory = Path(claude_home_override)
    else:
        claude_home_directory = Path.home() / claude_home_default_subdirectory
    return claude_home_directory.joinpath(*gate_script_relative_path)


def is_all_zeros_object_name(object_name: str) -> bool:
    all_zeros_object_name_character = ALL_ZEROS_OBJECT_NAME_CHARACTER
    stripped_object_name = object_name.strip()
    if not stripped_object_name:
        return True
    return all(
        each_character == all_zeros_object_name_character
        for each_character in stripped_object_name
    )


def resolve_base_reference_from_stdin(stdin_text: str) -> str:
    stdin_line_field_count = STDIN_LINE_FIELD_COUNT
    stdin_remote_object_field_index = STDIN_REMOTE_OBJECT_FIELD_INDEX
    default_remote_base_reference = DEFAULT_REMOTE_BASE_REFERENCE
    for each_line in stdin_text.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        fields = stripped_line.split()
        if len(fields) < stdin_line_field_count:
            continue
        remote_object_name = fields[stdin_remote_object_field_index]
        if not is_all_zeros_object_name(remote_object_name):
            return remote_object_name
    return default_remote_base_reference


def invoke_gate(gate_script_path: Path, base_reference: str) -> int:
    base_reference_argument = BASE_REFERENCE_ARGUMENT
    completion = subprocess.run(
        [
            sys.executable,
            str(gate_script_path),
            base_reference_argument,
            base_reference,
        ],
        check=False,
    )
    return completion.returncode


def main() -> int:
    gate_infrastructure_failure_exit_code = GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
    gate_script_path = resolve_gate_script_path()
    if not gate_script_path.is_file():
        return 0
    base_reference = resolve_base_reference_from_stdin(sys.stdin.read())
    gate_exit_code = invoke_gate(gate_script_path, base_reference)
    if gate_exit_code == gate_infrastructure_failure_exit_code:
        return 0
    return gate_exit_code


if __name__ == "__main__":
    sys.exit(main())
