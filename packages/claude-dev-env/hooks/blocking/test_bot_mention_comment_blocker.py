"""Unit tests for bot-mention-comment-blocker PreToolUse hook."""

import importlib.util
import json
import io
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "bot_mention_comment_blocker",
    _HOOK_DIR / "bot_mention_comment_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

_detect_bot_mention = hook_module._detect_bot_mention
_body_contains_token = hook_module._body_contains_token
_CORRECTIVE_MESSAGE_CURSOR = hook_module._CORRECTIVE_MESSAGE_CURSOR
_CORRECTIVE_MESSAGE_COPILOT = hook_module._CORRECTIVE_MESSAGE_COPILOT
_CURSOR_MENTION_TOKEN = hook_module._CURSOR_MENTION_TOKEN


def test_passes_clean_body() -> None:
    assert _detect_bot_mention("bugbot run") is None


def test_passes_empty_body() -> None:
    assert _detect_bot_mention("") is None


def test_passes_unrelated_body() -> None:
    assert _detect_bot_mention("please review this PR") is None


def test_blocks_cursor_mention() -> None:
    reason = _detect_bot_mention("@cursor bugbot run")
    assert reason is not None
    assert "bugbot run" in reason


def test_blocks_cursor_bracket_mention() -> None:
    reason = _detect_bot_mention("@cursor[bot] bugbot run")
    assert reason is not None
    assert "bugbot run" in reason


def test_blocks_copilot_mention() -> None:
    reason = _detect_bot_mention("@copilot review this")
    assert reason is not None
    assert "copilot-pull-request-reviewer" in reason


def test_returns_cursor_message_for_cursor() -> None:
    assert _detect_bot_mention("@cursor run") == _CORRECTIVE_MESSAGE_CURSOR


def test_returns_copilot_message_for_copilot() -> None:
    assert _detect_bot_mention("@copilot help") == _CORRECTIVE_MESSAGE_COPILOT


def test_copilot_wins_when_both_present() -> None:
    assert _detect_bot_mention("@cursor and @copilot") == _CORRECTIVE_MESSAGE_COPILOT


def test_body_contains_token_case_insensitive() -> None:
    assert _body_contains_token("Hello @CURSOR world", "@cursor")
    assert _body_contains_token("Hello @CoPilot world", "@copilot")


def test_body_contains_token_no_at_sign() -> None:
    assert not _body_contains_token("cursor without at-sign", _CURSOR_MENTION_TOKEN)
