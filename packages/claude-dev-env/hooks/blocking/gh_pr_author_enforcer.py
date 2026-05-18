#!/usr/bin/env python3
"""PreToolUse hook: auto-switch the active gh CLI account to GITHUB_DEFAULT_ACCOUNT for `gh pr create`.

Pinning every PR to a single canonical author makes the /bugteam and /qbug
follow-up swap deterministic. Those skills refuse to post REQUEST_CHANGES
reviews when the active gh CLI account matches the PR author (the GitHub
API returns HTTP 422 — "cannot review own pull request"). When every PR
has the same author, the swap step before bugteam is the same single
command every time.

Behavior:
- No-op when the bash command does not invoke `gh pr create`.
- No-op when `--web` / `-w` is present, since the browser flow does not
  create the PR via the gh CLI token.
- No-op when GITHUB_DEFAULT_ACCOUNT is unset (other users without this
  workflow are unaffected).
- No-op when the active gh account cannot be determined (gh missing,
  network failure) — defers to gh's own error path rather than blocking
  a command that may already be broken for other reasons.
- No-op when the active gh account already equals GITHUB_DEFAULT_ACCOUNT.
- Otherwise runs `gh auth switch --user <required>` silently and writes
  a per-session state file recording the original account. The PostToolUse
  companion (gh_pr_author_restore.py) reads that state file and swaps
  back after `gh pr create` finishes. On switch failure the hook falls
  back to the deny payload with the manual command.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile  # noqa: F401
from pathlib import Path

_hooks_tree_path = str(Path(__file__).resolve().parent.parent)
if _hooks_tree_path not in sys.path:
    sys.path.insert(0, _hooks_tree_path)

from _gh_pr_author_swap_utils import (  # noqa: E402  # sys.path shim above must run first
    _all_gh_pr_create_segments,
    _command_invokes_gh_pr_create,
    _delete_state_file,
    _state_file_path,
    _strip_quoted_regions,
    _switch_gh_account,
    _write_line,
)
from config.gh_pr_author_swap_constants import (  # noqa: E402  # sys.path shim above must run first
    ALL_GH_API_USER_COMMAND,
    BASH_TOOL_NAME,
    GH_API_USER_TIMEOUT_SECONDS,
    OS_O_NOFOLLOW_ATTRIBUTE_NAME,
    REQUIRED_ACCOUNT_ENV_VAR,
    STATE_FILE_ORIGINAL_ACCOUNT_KEY,
    STATE_FILE_PERMISSION_MODE,
    STATE_FILE_PRIMARY_ACCOUNT_KEY,
    WEB_FLAG_PATTERN,
)


def _active_gh_account() -> str | None:
    """Return the login of the active gh CLI account, or None when undetermined.

    Returns:
        The login string from ``gh api user --jq .login`` on success.
        None when gh is missing, the command fails, times out, or returns
        an empty value. The caller treats None as "skip the check."
    """
    try:
        completed_process = subprocess.run(
            list(ALL_GH_API_USER_COMMAND),
            capture_output=True,
            text=True,
            timeout=GH_API_USER_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if completed_process.returncode != 0:
        return None
    stripped_login = completed_process.stdout.strip()
    return stripped_login or None


def _write_swap_state(
    state_file: Path,
    original_account: str,
    primary_account: str,
) -> bool:
    """Persist the swap-back state for the PostToolUse restore hook.

    The state file is created atomically with ``os.open`` using
    ``O_WRONLY | O_CREAT | O_EXCL`` (plus ``O_NOFOLLOW`` on platforms
    that expose it) so an attacker on a shared POSIX workstation cannot
    pre-create the predictable path as a symlink pointing at an
    arbitrary writable file. The mode bits are set at create time so
    the file is never momentarily world-readable between ``open`` and
    ``chmod``. A defense-in-depth ``chmod`` call follows the write in
    case the platform's umask honored the ``mode`` argument differently
    than expected.

    A stale file left by a crashed prior session can collide with the
    ``O_EXCL`` guard. The function unlinks such a file and retries the
    create exactly once; a second collision is treated as a write
    failure so the caller does not silently overwrite something it did
    not create.

    A failure after a successful write unlinks the partially-written
    file via ``_delete_state_file`` before returning False so the caller
    does not leave a world-readable state file behind for the
    SessionStart cleanup hook to later pick up and trigger an unexpected
    ``gh auth switch``.

    Args:
        state_file: Destination path returned by ``_state_file_path``.
        original_account: Login that was active before the swap.
        primary_account: Login swapped to (always ``GITHUB_DEFAULT_ACCOUNT``).

    Returns:
        True when the atomic create, write, and chmod all succeed.
        False on any filesystem failure. A failure at any stage unlinks
        any partially-written file so the caller does not leave a
        world-readable state file behind.
    """
    swap_state = {
        STATE_FILE_ORIGINAL_ACCOUNT_KEY: original_account,
        STATE_FILE_PRIMARY_ACCOUNT_KEY: primary_account,
    }
    serialized_payload = json.dumps(swap_state).encode("utf-8")
    open_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, OS_O_NOFOLLOW_ATTRIBUTE_NAME):
        open_flags |= os.O_NOFOLLOW
    file_descriptor = _open_state_file_with_retry(state_file, open_flags)
    if file_descriptor is None:
        return False
    try:
        os.write(file_descriptor, serialized_payload)
    except OSError:
        os.close(file_descriptor)
        _delete_state_file(state_file)
        return False
    os.close(file_descriptor)
    try:
        os.chmod(state_file, STATE_FILE_PERMISSION_MODE)
    except OSError:
        _delete_state_file(state_file)
        return False
    return True


def _open_state_file_with_retry(state_file: Path, open_flags: int) -> int | None:
    """Open the state file atomically, unlinking a stale collision once.

    The enforcer can race against a state file left behind by a prior
    crashed session at the same predictable path. The first ``O_EXCL``
    open raises ``FileExistsError`` in that case; the function unlinks
    the stale file and retries exactly once. A second ``FileExistsError``
    is treated as a genuine race against a concurrent process and
    surfaces as ``None`` so the caller can fall back to its deny path.

    Args:
        state_file: Destination path returned by ``_state_file_path``.
        open_flags: Bitmask passed to ``os.open`` — must include
            ``O_EXCL`` so this retry logic can distinguish "stale file
            collision" from "wrote a fresh file".

    Returns:
        A file descriptor on success. ``None`` when both the initial
        open and the post-unlink retry fail.
    """
    try:
        return os.open(state_file, open_flags, STATE_FILE_PERMISSION_MODE)
    except FileExistsError:
        try:
            state_file.unlink()
        except OSError:
            return None
    except OSError:
        return None
    try:
        return os.open(state_file, open_flags, STATE_FILE_PERMISSION_MODE)
    except OSError:
        return None


def _build_switch_failure_message(required_account: str, current_account: str) -> str:
    """Build the deny reason emitted when the silent auto-switch fails.

    Args:
        required_account: Value of GITHUB_DEFAULT_ACCOUNT.
        current_account: Login returned by gh before the failed switch.

    Returns:
        A multi-line corrective message naming both accounts and giving
        the exact ``gh auth switch`` command the user should run.
    """
    return (
        f"BLOCKED [gh-pr-author]: tried to auto-switch the active gh CLI "
        f"account from `{current_account}` to `{required_account}` so "
        f"`gh pr create` would author from the canonical account, but "
        f"`gh auth switch` failed.\n\n"
        f"  Current:  {current_account}\n"
        f"  Required: {required_account}  (from ${REQUIRED_ACCOUNT_ENV_VAR})\n\n"
        f"Run first:\n"
        f"  gh auth switch --user {required_account}\n\n"
        f"If you genuinely want to author this PR from a different account "
        f"in this one case, switch to that account and retry. To create the "
        f"PR through the browser instead (uses your browser's GitHub session, "
        f"not the gh CLI token), add `--web`."
    )


def _build_state_write_failure_message(
    required_account: str,
    current_account: str,
    state_file: Path,
) -> str:
    """Build the deny reason emitted when state-file persistence fails after a successful swap.

    Args:
        required_account: Value of GITHUB_DEFAULT_ACCOUNT (the swap target).
        current_account: Login that was active before the swap (the
            restore target the failed state file should have recorded).
        state_file: Path the enforcer tried and failed to write.

    Returns:
        A multi-line corrective message explaining that the swap was
        attempted and reversed, so the PR command is being denied to
        prevent leaving the user on the wrong account. The reverse-switch
        may itself have failed; the message tells the user to verify the
        active account manually and gives the exact ``gh auth switch``
        command needed to recover.
    """
    return (
        f"BLOCKED [gh-pr-author]: swapped the active gh CLI account "
        f"from `{current_account}` to `{required_account}` so "
        f"`gh pr create` would author from the canonical account, but "
        f"writing the per-session state file used to restore the prior "
        f"account afterward failed. The swap was reversed to put "
        f"`{current_account}` back in place, and `gh pr create` is being "
        f"denied to prevent leaving the workflow in an inconsistent state.\n\n"
        f"  Current (intended):   {current_account}\n"
        f"  Required:             {required_account}  (from ${REQUIRED_ACCOUNT_ENV_VAR})\n"
        f"  State file (failed):  {state_file}\n\n"
        f"Verify the active account and recover manually if the reverse-switch "
        f"also failed:\n"
        f"  gh auth status\n"
        f"  gh auth switch --user {current_account}\n\n"
        f"Then re-run `gh pr create` so the enforcer can retry the swap."
    )


def _command_uses_web_flag(command: str) -> bool:
    """Return True when EVERY ``gh pr create`` segment uses ``--web`` / ``-w``.

    The flag is only relevant when it modifies the ``gh pr create``
    invocation itself. A ``-w`` token belonging to an unrelated command
    (for example ``curl -w '%{http_code}'``) before ``gh pr create``, or
    a flag attached to a chained command after a separator like ``&&`` /
    ``||`` / ``;`` / ``|`` / newline, must not flip the enforcer into
    the browser-flow no-op path. A ``-w`` sitting inside a quoted
    argument (for example ``--body "see -w docs"``) likewise must not
    match.

    When the command chains multiple ``gh pr create`` invocations
    (``gh pr create --web && gh pr create --title T``), the enforcer
    must trigger as long as ANY of them omits the web flag — otherwise
    the second invocation would slip through under the active account.
    A short-circuiting ``all()`` over every segment gives that
    "browser-flow only when EVERY segment opts in" semantics.

    Args:
        command: Raw bash command string from PreToolUse hook input.

    Returns:
        True when every ``gh pr create`` segment in ``command`` carries
        ``--web`` or ``-w`` as a whole token (with quoted regions
        stripped before the scan). False when ``gh pr create`` is
        absent, or when any segment lacks the flag.
    """
    quote_stripped_command = _strip_quoted_regions(command)
    all_gh_pr_create_segments = _all_gh_pr_create_segments(quote_stripped_command)
    if not all_gh_pr_create_segments:
        return False
    return all(
        bool(WEB_FLAG_PATTERN.search(each_segment))
        for each_segment in all_gh_pr_create_segments
    )


def _emit_deny_payload(reason_text: str) -> None:
    """Write the JSON deny payload to stdout for Claude Code to consume.

    Args:
        reason_text: User-facing explanation displayed by Claude Code.
    """
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason_text,
        }
    }
    _write_line(json.dumps(deny_payload), sys.stdout)


def main() -> None:
    """Read PreToolUse hook input on stdin and auto-switch the gh account when warranted.

    Exits 0 in all paths. On the silent-switch success path no output is
    produced. On switch-failure the JSON deny payload is written to
    stdout. On every no-op condition nothing is written.
    """
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("tool_name") != BASH_TOOL_NAME:
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    if not _command_invokes_gh_pr_create(command):
        sys.exit(0)

    if _command_uses_web_flag(command):
        sys.exit(0)

    required_account = os.environ.get(REQUIRED_ACCOUNT_ENV_VAR, "").strip()
    if not required_account:
        sys.exit(0)

    current_account = _active_gh_account()
    if current_account is None:
        sys.exit(0)
    if current_account == required_account:
        sys.exit(0)

    has_switched_account = _switch_gh_account(required_account)
    if not has_switched_account:
        _emit_deny_payload(
            _build_switch_failure_message(required_account, current_account)
        )
        sys.exit(0)

    session_id = str(hook_input.get("session_id") or "")
    state_file = _state_file_path(session_id)
    has_written_state = _write_swap_state(
        state_file,
        original_account=current_account,
        primary_account=required_account,
    )
    if not has_written_state:
        _switch_gh_account(current_account)
        _emit_deny_payload(
            _build_state_write_failure_message(
                required_account,
                current_account,
                state_file,
            )
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
