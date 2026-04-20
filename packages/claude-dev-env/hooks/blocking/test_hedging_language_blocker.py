"""Tests for hedging_language_blocker hook response shape."""

import json
import os
import subprocess
import sys

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "hedging_language_blocker.py")
EXPECTED_USER_FACING_MESSAGE = "Agent was found guessing - sourcing opinions..."
RESEARCH_MODE_SKILL_BODY_MARKER = "Three anti-hallucination constraints are ALWAYS active."
HEDGING_MESSAGE = "This is likely correct."
CLEAN_MESSAGE = "This is verified by the source document."
EMPTY_MESSAGE = ""


def run_hook_with_message(assistant_message: str) -> subprocess.CompletedProcess:
    hook_input_payload = json.dumps({"last_assistant_message": assistant_message})
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=hook_input_payload,
        capture_output=True,
        text=True,
        check=False,
    )


def test_hedging_message_emits_block_with_short_user_notice():
    completed_process = run_hook_with_message(HEDGING_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert parsed_response["systemMessage"] == EXPECTED_USER_FACING_MESSAGE
    assert parsed_response["suppressOutput"] is True
    assert "likely" in parsed_response["reason"]


def test_hedging_message_reason_contains_skill_path_not_body():
    completed_process = run_hook_with_message(HEDGING_MESSAGE)
    parsed_response = json.loads(completed_process.stdout)

    assert "research-mode" in parsed_response["reason"]
    assert "SKILL.md" in parsed_response["reason"]
    assert RESEARCH_MODE_SKILL_BODY_MARKER not in parsed_response["reason"]


def test_clean_message_passes_through_with_no_output():
    completed_process = run_hook_with_message(CLEAN_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_empty_message_passes_through_with_no_output():
    completed_process = run_hook_with_message(EMPTY_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""
