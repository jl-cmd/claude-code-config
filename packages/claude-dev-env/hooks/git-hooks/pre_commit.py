#!/usr/bin/env python3
"""Git pre-commit hook: run the CODE_RULES gate over staged changes.

Installed to the user's shared git-hooks directory via the claude-dev-env
installer; git invokes this file as `pre-commit` (the installer strips the
`_` and `.py` suffix when copying into the live hooks path).

Exit codes:
  0 - staged changes pass the gate (or the gate is not installed locally).
  1 - staged changes introduce one or more blocking violations.
  2 - unexpected invocation failure (e.g., subprocess could not launch).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


STAGED_SCOPE_ARGUMENT: str = "--staged"
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


def invoke_gate(gate_script_path: Path) -> int:
    completion = subprocess.run(
        [sys.executable, str(gate_script_path), STAGED_SCOPE_ARGUMENT],
        check=False,
    )
    return completion.returncode


def main() -> int:
    gate_script_path = resolve_gate_script_path()
    if not gate_script_path.is_file():
        return 0
    return invoke_gate(gate_script_path)


if __name__ == "__main__":
    sys.exit(main())
