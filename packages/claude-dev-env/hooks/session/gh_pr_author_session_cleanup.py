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

import os
import stat
import sys
import tempfile
import time
from pathlib import Path


_hooks_tree_path = str(Path(__file__).absolute().parent.parent)
if _hooks_tree_path not in sys.path:
    sys.path.insert(0, _hooks_tree_path)

from _gh_pr_author_swap_utils import (  # noqa: E402  # sys.path shim above must run first
    _delete_state_file,
    _read_original_account,
    _switch_gh_account,
    _write_line,
)
from config.gh_pr_author_swap_constants import (  # noqa: E402  # sys.path shim above must run first
    REQUIRED_ACCOUNT_ENV_VAR,
    STATE_FILE_PERMISSION_MODE,
    STATE_FILE_PREFIX,
    STATE_FILE_STALE_AGE_SECONDS,
    STATE_FILE_SUFFIX,
)


def _state_file_is_attacker_planted(file_lstat_result: os.stat_result) -> bool:
    """Return True when the file's owner or mode bits do not match an enforcer-written file.

    The enforcer atomically creates each swap-state file with mode
    ``STATE_FILE_PERMISSION_MODE`` (``0o600``) owned by the current
    user. A file in the shared system temp directory that diverges on
    either axis is overwhelmingly likely to be an attacker plant —
    another user on the same workstation pre-creating a file at the
    predictable swap-state path to trick the cleanup hook into running
    ``gh auth switch --user <attacker-controlled-login>``.

    Callers must pass an ``lstat`` result rather than a ``stat`` result.
    The enforcer creates state files with ``O_NOFOLLOW`` to prevent
    symlink hijacking; the cleanup hook must mirror that contract by
    inspecting the entry itself rather than what a symlink points to.
    Otherwise an attacker-planted symlink pointing to any 0o600 file
    owned by the current user (an SSH key, a token cache) would pass
    the ownership/mode check and drive ``gh auth switch`` to an
    attacker-influenced account.

    The mode-bit and uid checks only apply on POSIX. Windows reports
    ``0o666`` from ``stat`` for files chmod'd to ``0o600`` because
    ``os.chmod`` on Windows only toggles the read-only attribute, and
    ``os.getuid`` is absent there. ``tempfile.gettempdir()`` on Windows
    is already per-user (``%LOCALAPPDATA%\\Temp``), which closes the
    cross-user attack surface this check guards against on POSIX, so
    the check is a no-op on Windows.

    Args:
        file_lstat_result: ``os.stat_result`` produced by ``lstat`` for
            the candidate file. Symlinks must reach this function as
            their own entry, not as their resolved target.

    Returns:
        True when the file looks attacker-planted (POSIX: wrong mode
        bits or wrong uid). False when the file matches the enforcer's
        write contract, or when running on a platform without POSIX
        ownership semantics.
    """
    if not hasattr(os, "getuid"):
        return False
    actual_permission_bits = stat.S_IMODE(file_lstat_result.st_mode)
    if actual_permission_bits != STATE_FILE_PERMISSION_MODE:
        return True
    current_user_id = os.getuid()
    if file_lstat_result.st_uid != current_user_id:
        return True
    return False


def _collect_stale_state_files(temp_directory: Path) -> list[Path]:
    """Return swap-state files older than the stale threshold and safe to process.

    A state file younger than ``STATE_FILE_STALE_AGE_SECONDS`` is
    treated as belonging to a concurrent Claude Code session that may
    still be mid-``gh pr create``. Sweeping such a file would steal the
    active session's restore target. Files older than the threshold are
    overwhelmingly likely to be stale — the enforcer-to-restore window
    is bounded by the gh subprocess timeouts (10s switch + 5s api user
    + filesystem work), so any file older than 60s is past the longest
    plausible active window.

    Each candidate is also screened for ownership and permission bits
    matching the enforcer's write contract. A file with mode bits other
    than ``STATE_FILE_PERMISSION_MODE`` or (on POSIX) owned by a
    different user is silently skipped — it was not written by an
    enforcer running as the current user and must not be allowed to
    drive ``gh auth switch``.

    The candidate is inspected via ``lstat`` rather than ``stat`` so a
    symlink at the predictable swap-state path is screened on its own
    metadata, not on whatever the symlink resolves to. Any entry that
    is not a regular file (symlink, socket, fifo, device) is silently
    skipped. The enforcer creates state files with ``O_NOFOLLOW``;
    mirroring that contract here closes the symlink-hijack window where
    an attacker plants a symlink pointing to a legitimate 0o600 file
    owned by the current user to trick the cleanup hook into reading
    that file as a swap-state payload.

    Args:
        temp_directory: System temp directory returned by
            ``tempfile.gettempdir()``.

    Returns:
        List of swap-state file paths that are regular files whose
        modification time is older than ``STATE_FILE_STALE_AGE_SECONDS``
        seconds before now and whose ownership/mode bits match the
        enforcer's write contract. Empty list when the temp directory
        cannot be listed.
    """
    glob_pattern = f"{STATE_FILE_PREFIX}*{STATE_FILE_SUFFIX}"
    current_time_seconds = time.time()
    all_stale_state_files: list[Path] = []
    try:
        all_candidate_paths = sorted(temp_directory.glob(glob_pattern))
    except OSError:
        return []
    for each_candidate_path in all_candidate_paths:
        try:
            file_lstat_result = each_candidate_path.lstat()
        except OSError:
            continue
        if not stat.S_ISREG(file_lstat_result.st_mode):
            continue
        if _state_file_is_attacker_planted(file_lstat_result):
            continue
        file_age_seconds = current_time_seconds - file_lstat_result.st_mtime
        if file_age_seconds >= STATE_FILE_STALE_AGE_SECONDS:
            all_stale_state_files.append(each_candidate_path)
    return all_stale_state_files


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
    has_switched_account = _switch_gh_account(original_account)
    if has_switched_account:
        _delete_state_file(state_file)
    else:
        _write_line(
            f"[gh-pr-author-cleanup] failed to restore active gh account to {original_account!r} from "
            f"stale state file {state_file}; left in place for next session",
            sys.stderr,
        )


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
    all_stale_state_files = _collect_stale_state_files(temp_directory)
    for each_state_file in all_stale_state_files:
        _restore_stale_state_file(each_state_file)


if __name__ == "__main__":
    main()
