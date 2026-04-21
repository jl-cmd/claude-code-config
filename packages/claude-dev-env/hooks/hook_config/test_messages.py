"""Smoke tests for hook_config.messages — verify user-facing notice constants exist."""

from hook_config import messages


def test_user_facing_notice_is_nonempty_string() -> None:
    assert isinstance(messages.USER_FACING_NOTICE, str)
    assert messages.USER_FACING_NOTICE


def test_user_facing_tdd_notice_is_nonempty_string() -> None:
    assert isinstance(messages.USER_FACING_TDD_NOTICE, str)
    assert messages.USER_FACING_TDD_NOTICE
