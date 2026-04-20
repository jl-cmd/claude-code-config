from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import config


def test_gate_infrastructure_failure_exit_code_is_distinct_from_violation_and_success() -> (
    None
):
    assert config.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE != 0
    assert config.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE != 1
