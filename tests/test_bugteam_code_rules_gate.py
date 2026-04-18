from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = (
    REPO_ROOT
    / "packages"
    / "claude-dev-env"
    / "skills"
    / "bugteam"
    / "scripts"
    / "bugteam_code_rules_gate.py"
)


def test_gate_help_exits_zero() -> None:
    completed = subprocess.run(
        [sys.executable, str(GATE_SCRIPT), "--help"],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
