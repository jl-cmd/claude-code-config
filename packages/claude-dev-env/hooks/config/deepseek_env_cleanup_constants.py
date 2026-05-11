"""Configuration constants for the deepseek_env_cleanup SessionStart hook."""

from __future__ import annotations

ALL_ANTHROPIC_ENV_VAR_NAMES_DETECTED: tuple[str, ...] = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "CLAUDE_CODE_EFFORT_LEVEL",
)

ALL_LOOPBACK_HOSTS: tuple[str, ...] = ("127.0.0.1", "localhost")

PROXY_CONNECT_TIMEOUT_SECONDS: float = 1.0

ANTHROPIC_BASE_URL_ENV_VAR_NAME: str = "ANTHROPIC_BASE_URL"
