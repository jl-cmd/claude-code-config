#!/usr/bin/env python3
"""Sync the canonical .github/workflows/claude.yml to every downstream caller repo.

The canonical wrapper lives in this repository. Downstream repos never edit their
own caller — this script pushes the identical file contents via the GitHub Contents
API using the `gh` CLI. Run after any change to the canonical wrapper.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sync_claude_workflow.engine import main as run_sync_claude_workflow

if __name__ == "__main__":
    sys.exit(run_sync_claude_workflow())
