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

import subprocess
import sys
from pathlib import Path

from config import STAGED_SCOPE_ARGUMENT
from gate_utils import resolve_gate_script_path


def invoke_gate(gate_script_path: Path) -> int:
    staged_scope_argument = STAGED_SCOPE_ARGUMENT
    completion = subprocess.run(
        [sys.executable, str(gate_script_path), staged_scope_argument],
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
