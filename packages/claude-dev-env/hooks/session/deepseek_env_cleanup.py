"""SessionStart hook: detect stale DeepSeek proxy environment variables.

When ``cc deepseek`` exits abnormally (terminal killed, double Ctrl+C, crash),
the launcher's ``finally`` block never runs, leaving ``ANTHROPIC_BASE_URL``
pointing to a dead proxy and model-name overrides still set in the shell process.

This hook probes the proxy address at session start and exits non-zero when
the proxy is unreachable so the harness surfaces a diagnostic. The actual
env-var cleanup happens in cc-launcher.ps1 where it can modify the parent
PowerShell process environment.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = str(Path(__file__).resolve().parent.parent)
    if hooks_tree not in sys.path:
        sys.path.insert(0, hooks_tree)


_insert_hooks_tree_for_imports()

from config.deepseek_env_cleanup_constants import (
    ALL_ANTHROPIC_ENV_VAR_NAMES_DETECTED,
    ALL_LOOPBACK_HOSTS,
    ANTHROPIC_BASE_URL_ENV_VAR_NAME,
    PROXY_CONNECT_TIMEOUT_SECONDS,
)


def _is_proxy_listening(host: str, port: int, timeout_seconds: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _parse_proxy_address(base_url: str) -> tuple[str, int] | None:
    parsed = urlparse(base_url)
    if parsed.hostname is None:
        return None
    if parsed.hostname.lower() not in ALL_LOOPBACK_HOSTS:
        return None
    port = parsed.port
    if port is None:
        return None
    return (parsed.hostname, port)


def _count_stale_env_vars() -> int:
    count = 0
    for each_var_name in ALL_ANTHROPIC_ENV_VAR_NAMES_DETECTED:
        if each_var_name in os.environ:
            count += 1
    return count


def main() -> int:
    """Probe the proxy address and return 1 when stale env vars are detected.

    Returns:
        0 when clean or not applicable, 1 when stale vars are present.
    """
    base_url = os.environ.get(ANTHROPIC_BASE_URL_ENV_VAR_NAME)
    if not base_url:
        return 0
    proxy_address = _parse_proxy_address(base_url)
    if proxy_address is None:
        return 0
    host, port = proxy_address
    if _is_proxy_listening(host, port, PROXY_CONNECT_TIMEOUT_SECONDS):
        return 0
    stale_count = _count_stale_env_vars()
    if stale_count:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
