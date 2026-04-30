"""Shared helpers for invoking GitHub CLI with basic resiliency."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.modules.pop("config", None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.gh_util_constants import (
    ALL_AUTH_ERROR_MARKERS,
    ALL_TRANSIENT_ERROR_MARKERS,
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
    EXPONENTIAL_BACKOFF_BASE,
    GH_TIMEOUT_RETURN_CODE,
    INLINE_REVIEW_COMMENTS_PATH_TEMPLATE,
)


@dataclass(frozen=True)
class GhResult:
    returncode: int
    stdout: str
    stderr: str
    is_timed_out: bool = False


def _is_transient_error(message: str) -> bool:
    lowered = message.lower()
    return any(each_marker in lowered for each_marker in ALL_TRANSIENT_ERROR_MARKERS)


def _is_auth_error(message: str) -> bool:
    lowered = message.lower()
    return any(each_marker in lowered for each_marker in ALL_AUTH_ERROR_MARKERS)


def _ensure_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def run_gh(
    all_command: Sequence[str],
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> GhResult:
    """Run a gh command with timeout + transient retry handling.

    Retries are attempted only for transient failures (network/server/rate-limit style
    messages). Auth/scope failures are returned immediately to fail closed.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    max_attempts = DEFAULT_RETRIES + 1
    for each_attempt in range(max_attempts):
        try:
            gh_completion = subprocess.run(
                all_command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            error_stderr = _ensure_text(error.stderr)
            error_stdout = _ensure_text(error.stdout)
            message = (
                error_stderr or error_stdout or ""
            ).strip() or "gh command timed out"
            last_result = GhResult(
                returncode=GH_TIMEOUT_RETURN_CODE,
                stdout="",
                stderr=message,
                is_timed_out=True,
            )
            if each_attempt < max_attempts - 1:
                time.sleep(
                    DEFAULT_BACKOFF_SECONDS
                    * (EXPONENTIAL_BACKOFF_BASE**each_attempt)
                )
                continue
            return last_result

        gh_result = GhResult(
            returncode=gh_completion.returncode,
            stdout=gh_completion.stdout,
            stderr=gh_completion.stderr,
        )
        if gh_result.returncode == 0:
            return gh_result

        combined = f"{gh_result.stderr}\n{gh_result.stdout}".strip()
        if _is_auth_error(combined):
            return gh_result
        if each_attempt < max_attempts - 1 and _is_transient_error(combined):
            time.sleep(
                DEFAULT_BACKOFF_SECONDS * (EXPONENTIAL_BACKOFF_BASE**each_attempt)
            )
            continue
        return gh_result
    return GhResult(
        returncode=GH_TIMEOUT_RETURN_CODE,
        stdout="",
        stderr="gh command exhausted all attempts",
        is_timed_out=True,
    )


def fetch_inline_review_comments(
    owner: str,
    repo: str,
    pull_number: int,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, object]] | None:
    """Fetch inline review comments for a pull request from the GitHub API.

    Returns the parsed list of comment objects on success, or None when the
    gh call fails or returns invalid/unexpected JSON. This preserves the
    distinction between "no inline comments" and "unable to determine
    inline comments".
    """
    api_path = INLINE_REVIEW_COMMENTS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, pull_number=pull_number
    )
    fetch_result = run_gh(
        [
            "gh",
            "-R",
            f"{owner}/{repo}",
            "api",
            api_path,
            "--paginate",
        ],
        timeout_seconds=timeout_seconds,
    )
    if fetch_result.returncode != 0:
        return None
    try:
        parsed = json.loads(fetch_result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    return parsed


def parse_owner_repo(repository: str) -> tuple[str, str]:
    if "/" not in repository:
        raise ValueError("repository must be owner/repo with exactly one slash")
    owner, name = repository.split("/", maxsplit=1)
    if not owner or not name:
        raise ValueError("repository must be owner/repo with exactly one slash")
    if "/" in name:
        raise ValueError("repository must be owner/repo with exactly one slash")
    return owner, name
