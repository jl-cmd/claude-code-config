"""Tests for deepseek_env_cleanup SessionStart hook."""

from __future__ import annotations

import socket
from unittest import mock

import pytest

from config.deepseek_env_cleanup_constants import (
    ALL_ANTHROPIC_ENV_VAR_NAMES_DETECTED,
)
from session.deepseek_env_cleanup import (
    _count_stale_env_vars,
    _is_proxy_listening,
    _parse_proxy_address,
    main,
)


def test_parse_proxy_address_returns_none_for_empty_url() -> None:
    assert _parse_proxy_address("") is None


def test_parse_proxy_address_returns_none_for_no_hostname() -> None:
    assert _parse_proxy_address("not-a-url") is None


def test_parse_proxy_address_returns_host_and_port_for_localhost() -> None:
    result = _parse_proxy_address("http://127.0.0.1:54022")
    assert result == ("127.0.0.1", 54022)


def test_parse_proxy_address_returns_host_and_port_for_dns_name() -> None:
    result = _parse_proxy_address("http://localhost:54022")
    assert result == ("localhost", 54022)


def test_parse_proxy_address_returns_none_for_non_loopback() -> None:
    assert _parse_proxy_address("http://api.deepseek.com:443") is None


def test_parse_proxy_address_returns_none_when_port_missing() -> None:
    assert _parse_proxy_address("http://127.0.0.1") is None


@mock.patch("socket.create_connection")
def test_is_proxy_listening_returns_true_on_success(
    mock_create_connection: mock.MagicMock,
) -> None:
    assert _is_proxy_listening("127.0.0.1", 54022, 1.0) is True


@mock.patch("socket.create_connection")
def test_is_proxy_listening_returns_false_on_refused(
    mock_create_connection: mock.MagicMock,
) -> None:
    mock_create_connection.side_effect = ConnectionRefusedError
    assert _is_proxy_listening("127.0.0.1", 54022, 1.0) is False


@mock.patch("socket.create_connection")
def test_is_proxy_listening_returns_false_on_timeout(
    mock_create_connection: mock.MagicMock,
) -> None:
    mock_create_connection.side_effect = socket.timeout
    assert _is_proxy_listening("127.0.0.1", 54022, 1.0) is False


def test_count_stale_vars_counts_all_anthropic_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for each_var_name in ALL_ANTHROPIC_ENV_VAR_NAMES_DETECTED:
        monkeypatch.setenv(each_var_name, "test-value")
    assert _count_stale_env_vars() == len(ALL_ANTHROPIC_ENV_VAR_NAMES_DETECTED)


def test_count_stale_vars_returns_zero_when_nothing_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for each_var_name in ALL_ANTHROPIC_ENV_VAR_NAMES_DETECTED:
        monkeypatch.delenv(each_var_name, raising=False)
    assert _count_stale_env_vars() == 0


def test_main_returns_zero_when_base_url_not_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    assert main() == 0


@mock.patch("session.deepseek_env_cleanup._is_proxy_listening")
def test_main_returns_one_when_proxy_is_dead(
    mock_is_listening: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:54022")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
    mock_is_listening.return_value = False
    assert main() == 1


@mock.patch("session.deepseek_env_cleanup._is_proxy_listening")
def test_main_returns_zero_when_proxy_is_alive(
    mock_is_listening: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:54022")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
    mock_is_listening.return_value = True
    assert main() == 0
