"""Tests for pr_converge_constants.

Verifies that login/state constants carry the expected values, and the bugbot
regex matches dirty review bodies but not clean ones.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "pr_converge_constants.py"
    spec = importlib.util.spec_from_file_location("pr_converge_constants", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pr_converge_constants_module = _load_module()


def test_bugbot_dirty_body_regex_distinguishes_findings_from_clean_bodies() -> None:
    dirty_body = "Cursor Bugbot has reviewed your changes and found 3 potential issues."
    clean_body = "Bugbot reviewed your changes and found no new issues!"
    compiled_pattern = re.compile(pr_converge_constants_module.BUGBOT_DIRTY_BODY_REGEX)
    dirty_match = compiled_pattern.search(dirty_body)
    assert dirty_match is not None
    assert "found 3 potential issue" in dirty_match.group(0)
    assert compiled_pattern.search(clean_body) is None


def test_cursor_bot_login_matches_github_login_string() -> None:
    assert pr_converge_constants_module.CURSOR_BOT_LOGIN == "cursor[bot]"


def test_copilot_reviewer_login_carries_bot_suffix() -> None:
    assert (
        pr_converge_constants_module.COPILOT_REVIEWER_LOGIN
        == "copilot-pull-request-reviewer[bot]"
    )


def test_copilot_reviewer_request_id_reuses_login_constant() -> None:
    request_id = pr_converge_constants_module.COPILOT_REVIEWER_REQUEST_ID
    login = pr_converge_constants_module.COPILOT_REVIEWER_LOGIN
    assert request_id == login
    assert request_id is login


def test_copilot_clean_review_state_is_approved() -> None:
    assert pr_converge_constants_module.COPILOT_CLEAN_REVIEW_STATE == "APPROVED"


def test_copilot_dirty_review_states_lists_changes_requested_and_commented() -> None:
    dirty_states = pr_converge_constants_module.ALL_COPILOT_DIRTY_REVIEW_STATES
    assert "CHANGES_REQUESTED" in dirty_states
    assert "COMMENTED" in dirty_states


def test_copilot_soft_dirty_review_state_is_commented() -> None:
    assert pr_converge_constants_module.COPILOT_SOFT_DIRTY_REVIEW_STATE == "COMMENTED"


