from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import config


def test_new_message_constants_are_present_in_config() -> None:
    assert "{path}" in config.GATE_SCRIPT_NOT_FOUND_MESSAGE
    assert "{error}" in config.STDIN_READ_FAILURE_MESSAGE
    assert "{error}" in config.INVOKE_GATE_FAILURE_MESSAGE
    assert "{line" in config.MALFORMED_STDIN_LINE_MESSAGE


def test_pre_push_gate_script_not_found_message_contains_path_placeholder() -> None:
    assert "{path}" in config.PRE_PUSH_GATE_SCRIPT_NOT_FOUND_MESSAGE
