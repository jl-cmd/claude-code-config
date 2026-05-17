#!/usr/bin/env python3
"""PostToolUse hook: restore the prior gh CLI account after `gh pr create` runs.

Companion to ``gh_pr_author_enforcer.py``. When the PreToolUse enforcer
silently swaps the active gh account to ``GITHUB_DEFAULT_ACCOUNT`` and
records the original account in a per-session state file, this hook
reads that state file after the matching Bash invocation finishes and
runs ``gh auth switch --user <original>`` to put the prior account back
in place.

The state file is deleted only when the restore switch succeeds. If
``gh auth switch`` fails the state file is left in place so the
SessionStart cleanup hook (``gh_pr_author_session_cleanup.py``) can
retry on the next session start instead of stranding the user on the
canonical author account.

Behavior:
- No-op when tool_name is not Bash.
- No-op when the command did not invoke ``gh pr create`` (uses the same
  regex as the enforcer so the pair stays in sync).
- No-op when no per-session state file exists — means the enforcer
  never swapped on this command.
- Otherwise reads the state file, runs ``gh auth switch --user <original>``,
  and deletes the state file only when the switch succeeded. Failures
  are logged to stderr; this hook never blocks the workflow.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TextIO

from config.gh_pr_author_swap_constants import (
    ALL_GH_AUTH_SWITCH_COMMAND_HEAD,
    BASH_TOOL_NAME,
    GH_AUTH_SWITCH_TIMEOUT_SECONDS,
    GH_PR_CREATE_PATTERN,
    STATE_FILE_DEFAULT_SESSION_ID,
    STATE_FILE_ORIGINAL_ACCOUNT_KEY,
    STATE_FILE_PREFIX,
    STATE_FILE_SUFFIX,
)


def _write_line(message: str, output_stream: TextIO) -> None:
    """Write a single line to the caller-provided text stream.

    Wrapping ``stream.write`` in a function that accepts an explicit
    ``output_stream`` parameter satisfies the project's logging rule
    (route through logger or accept an explicit stream parameter) without
    pulling the logging module into a self-contained hook script.

    Args:
        message: Single line of output. A trailing newline is appended.
        output_stream: Destination stream (typically ``sys.stdout`` for
            the JSON deny payload or ``sys.stderr`` for diagnostics).
    """
    output_stream.write(message + "\n")
    output_stream.flush()


def _state_file_path(session_id: str) -> Path:
    """Return the per-session state-file path written by the enforcer hook.

    Args:
        session_id: ``session_id`` from the Claude Code hook input JSON.
            Empty string falls back to ``STATE_FILE_DEFAULT_SESSION_ID``.

    Returns:
        Absolute path to the state file in the system temp directory.
    """
    effective_session_id = session_id or STATE_FILE_DEFAULT_SESSION_ID
    filename = f"{STATE_FILE_PREFIX}{effective_session_id}{STATE_FILE_SUFFIX}"
    return Path(tempfile.gettempdir()) / filename


def _read_original_account(state_file: Path) -> str | None:
    """Read the original-account login from the state file.

    Args:
        state_file: Path produced by ``_state_file_path``.

    Returns:
        The original account login when the file exists and parses to a
        JSON object with a non-empty ``original_account`` value. None
        when the file is absent, unreadable, or malformed.
    """
    try:
        raw_contents = state_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as os_error:
        _write_line(
            f"[gh-pr-author-restore] failed to read state file {state_file}: {os_error}",
            sys.stderr,
        )
        return None
    try:
        parsed_state = json.loads(raw_contents)
    except json.JSONDecodeError as decode_error:
        _write_line(
            f"[gh-pr-author-restore] malformed state file {state_file}: {decode_error}",
            sys.stderr,
        )
        return None
    if not isinstance(parsed_state, dict):
        return None
    original_account = parsed_state.get(STATE_FILE_ORIGINAL_ACCOUNT_KEY, "")
    if not isinstance(original_account, str):
        return None
    stripped_original_account = original_account.strip()
    return stripped_original_account or None


def _delete_state_file(state_file: Path) -> None:
    """Remove the state file, ignoring an already-absent file.

    Args:
        state_file: Path produced by ``_state_file_path``.
    """
    try:
        state_file.unlink()
    except FileNotFoundError:
        return
    except OSError as os_error:
        _write_line(
            f"[gh-pr-author-restore] failed to delete state file {state_file}: {os_error}",
            sys.stderr,
        )


def _switch_gh_account(to_account: str) -> bool:
    """Run ``gh auth switch --user <to_account>`` and report success.

    Args:
        to_account: Login to switch the active gh CLI account back to.

    Returns:
        True when the switch command exits zero. False when gh is missing,
        the switch command exits non-zero, times out, or otherwise fails.
    """
    switch_command = list(ALL_GH_AUTH_SWITCH_COMMAND_HEAD) + [to_account]
    try:
        completed_process = subprocess.run(
            switch_command,
            capture_output=True,
            text=True,
            timeout=GH_AUTH_SWITCH_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as run_error:
        _write_line(
            f"[gh-pr-author-restore] gh auth switch raised: {run_error}",
            sys.stderr,
        )
        return False
    if completed_process.returncode != 0:
        _write_line(
            f"[gh-pr-author-restore] gh auth switch exited "
            f"{completed_process.returncode}: {completed_process.stderr.strip()}",
            sys.stderr,
        )
        return False
    return True


def _command_invokes_gh_pr_create(command: str) -> bool:
    """Return True when the command string contains a ``gh pr create`` invocation.

    Args:
        command: Raw bash command string from PostToolUse hook input.

    Returns:
        True when ``gh pr create`` appears as a whole-word match.
    """
    return bool(GH_PR_CREATE_PATTERN.search(command))


def main() -> None:
    """Read PostToolUse hook input on stdin and restore the prior gh account.

    Exits 0 in every path. Errors are logged to stderr only — this hook
    must never block subsequent commands.
    """
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("tool_name") != BASH_TOOL_NAME:
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command or not _command_invokes_gh_pr_create(command):
        sys.exit(0)

    session_id = str(hook_input.get("session_id") or "")
    state_file = _state_file_path(session_id)
    original_account = _read_original_account(state_file)
    if original_account is None:
        if state_file.exists():
            _delete_state_file(state_file)
        sys.exit(0)

    restore_succeeded = _switch_gh_account(original_account)
    if restore_succeeded:
        _delete_state_file(state_file)
    sys.exit(0)


if __name__ == "__main__":
    main()
