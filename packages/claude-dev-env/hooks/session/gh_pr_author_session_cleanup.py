#!/usr/bin/env python3
"""SessionStart hook — sweep stale gh-pr-author swap state files at session start.

The PreToolUse enforcer (``gh_pr_author_enforcer.py``) writes a per-session
state file recording the original gh CLI account before swapping to
``GITHUB_DEFAULT_ACCOUNT``. The PostToolUse companion
(``gh_pr_author_restore.py``) reads that file and switches back when
``gh pr create`` finishes. When a session is interrupted between the
swap and the restore — a crash, a downstream PreToolUse deny that fires
*after* the enforcer's swap completed, or any other path that skips
PostToolUse — the user is left on ``GITHUB_DEFAULT_ACCOUNT`` with a
stale state file on disk.

This hook runs at the start of every Claude Code session. When
``GITHUB_DEFAULT_ACCOUNT`` is set, it scans ``tempfile.gettempdir()``
for every file matching ``{STATE_FILE_PREFIX}*{STATE_FILE_SUFFIX}``,
reads the original account from each, runs ``gh auth switch --user
<original>``, and deletes the file. A state file whose switch fails is
left in place so the next session can retry. The hook is a strict no-op
when ``GITHUB_DEFAULT_ACCOUNT`` is unset, so users who have not opted
into the swap workflow are completely unaffected.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TextIO


def _insert_hooks_tree_for_imports() -> None:
    """Add the hooks/ tree to ``sys.path`` so ``config.*`` imports resolve.

    The SessionStart hook lives under ``hooks/session/`` and the shared
    configuration constants live under ``hooks/config/``. Adding the
    parent ``hooks/`` directory to ``sys.path`` lets the standard
    ``from config.<module> import ...`` form work whether the hook is
    invoked by Claude Code's hook runner or by pytest during local
    testing.
    """
    hooks_tree = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.gh_pr_author_swap_constants import (
    ALL_GH_AUTH_SWITCH_COMMAND_HEAD,
    GH_AUTH_SWITCH_TIMEOUT_SECONDS,
    REQUIRED_ACCOUNT_ENV_VAR,
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
        output_stream: Destination stream (typically ``sys.stderr`` for
            diagnostics, since this hook never blocks).
    """
    output_stream.write(message + "\n")
    output_stream.flush()


def _switch_gh_account(to_account: str) -> bool:
    """Run ``gh auth switch --user <to_account>`` and report success.

    Args:
        to_account: Login to switch the active gh CLI account back to.

    Returns:
        True when the switch command exits zero. False when gh is missing,
        the switch command exits non-zero, times out, or otherwise fails.
        Failure diagnostics are written to stderr so the user can see why
        a stale state file was kept for the next session to retry.
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
            f"[gh-pr-author-session-cleanup] gh auth switch raised: {run_error}",
            sys.stderr,
        )
        return False
    if completed_process.returncode != 0:
        _write_line(
            f"[gh-pr-author-session-cleanup] gh auth switch exited "
            f"{completed_process.returncode}: {completed_process.stderr.strip()}",
            sys.stderr,
        )
        return False
    return True


def _read_original_account(state_file: Path) -> str | None:
    """Read the original-account login from a swap-state file.

    Args:
        state_file: Absolute path to a candidate state file under the
            system temp directory.

    Returns:
        The original account login when the file exists and parses to a
        JSON object with a non-empty string ``original_account`` value.
        None when the file is unreadable, malformed JSON, the wrong
        shape, missing the key, holds a non-string value, or holds a
        blank value. The caller treats None as "no restore needed."
    """
    try:
        raw_contents = state_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as os_error:
        _write_line(
            f"[gh-pr-author-session-cleanup] failed to read state file {state_file}: {os_error}",
            sys.stderr,
        )
        return None
    try:
        parsed_state = json.loads(raw_contents)
    except json.JSONDecodeError as decode_error:
        _write_line(
            f"[gh-pr-author-session-cleanup] malformed state file {state_file}: {decode_error}",
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
    """Remove a stale state file, ignoring an already-absent file.

    Args:
        state_file: Absolute path to the state file to delete.
    """
    try:
        state_file.unlink()
    except FileNotFoundError:
        return
    except OSError as os_error:
        _write_line(
            f"[gh-pr-author-session-cleanup] failed to delete state file {state_file}: {os_error}",
            sys.stderr,
        )


def _all_stale_state_files(temp_directory: Path) -> list[Path]:
    """Return every swap-state file present under the temp directory.

    Args:
        temp_directory: System temp directory returned by
            ``tempfile.gettempdir()``.

    Returns:
        A list of absolute paths matching
        ``{STATE_FILE_PREFIX}*{STATE_FILE_SUFFIX}``. Empty list when the
        temp directory cannot be listed or contains no matches.
    """
    glob_pattern = f"{STATE_FILE_PREFIX}*{STATE_FILE_SUFFIX}"
    try:
        return sorted(temp_directory.glob(glob_pattern))
    except OSError:
        return []


def _restore_stale_state_file(state_file: Path) -> None:
    """Restore one stale state file: switch back, then delete on success.

    A malformed state file is deleted without a switch attempt. A
    well-formed file whose switch attempt fails is left on disk so the
    next session-start can retry.

    Args:
        state_file: Absolute path to a candidate state file.
    """
    original_account = _read_original_account(state_file)
    if original_account is None:
        _delete_state_file(state_file)
        return
    switch_succeeded = _switch_gh_account(original_account)
    if switch_succeeded:
        _delete_state_file(state_file)


def main() -> None:
    """Sweep stale gh-pr-author swap state files when the workflow is enabled.

    Exits 0 in every path. When ``GITHUB_DEFAULT_ACCOUNT`` is unset the
    hook returns immediately so users who have not opted into the swap
    workflow see no behavior change. Otherwise iterates every matching
    state file under ``tempfile.gettempdir()`` and restores each one
    independently — a failure on one file does not block the others.
    """
    required_account = os.environ.get(REQUIRED_ACCOUNT_ENV_VAR, "").strip()
    if not required_account:
        return
    temp_directory = Path(tempfile.gettempdir())
    all_stale_state_files = _all_stale_state_files(temp_directory)
    for each_state_file in all_stale_state_files:
        _restore_stale_state_file(each_state_file)


if __name__ == "__main__":
    main()
