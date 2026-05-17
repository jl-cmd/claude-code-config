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

from _gh_pr_author_swap_utils import (
    _command_invokes_gh_pr_create,
    _delete_state_file,
    _state_file_path,
    _strip_quoted_regions,
    _switch_gh_account,
    _write_line,
)
from config.gh_pr_author_swap_constants import (
    ALL_GH_API_USER_COMMAND,
    BASH_TOOL_NAME,
    COMMAND_SEPARATOR_PATTERN,
    GH_API_USER_TIMEOUT_SECONDS,
    GH_PR_CREATE_PATTERN,
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

    The state file is chmod'd to ``STATE_FILE_PERMISSION_MODE`` (``0o600``)
    immediately after the write so other accounts on a shared POSIX
    workstation cannot read which gh CLI account is in use. Windows
    ignores POSIX mode bits, so this is a no-op there — the primary
    target platform's ``tempfile.gettempdir()`` is already per-user
    (``%LOCALAPPDATA%\\Temp``).

    A chmod failure after a successful write unlinks the partially-written
    file via ``_delete_state_file`` before returning False so the caller
    does not leave a world-readable state file behind for the
    SessionStart cleanup hook to later pick up and trigger an unexpected
    ``gh auth switch``.

    Args:
        state_file: Destination path returned by ``_state_file_path``.
        original_account: Login that was active before the swap.
        primary_account: Login swapped to (always ``GITHUB_DEFAULT_ACCOUNT``).

    Returns:
        True when both the write and the permission chmod succeed. False
        on any filesystem failure. A chmod failure on a platform that
        honors POSIX modes is treated the same as a write failure so the
        caller does not leave a world-readable state file behind.
    """
    swap_state = {
        STATE_FILE_ORIGINAL_ACCOUNT_KEY: original_account,
        STATE_FILE_PRIMARY_ACCOUNT_KEY: primary_account,
    }
    try:
        state_file.write_text(json.dumps(swap_state), encoding="utf-8")
    except OSError:
        return False
    try:
        os.chmod(state_file, STATE_FILE_PERMISSION_MODE)
    except OSError:
        _delete_state_file(state_file)
        return False
    return True


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
    """Return True when ``--web`` / ``-w`` appears inside the ``gh pr create`` segment.

    The flag is only relevant when it modifies the ``gh pr create``
    invocation itself. A ``-w`` token belonging to an unrelated command
    (for example ``curl -w '%{http_code}'``) before ``gh pr create``, or
    a flag attached to a chained command after a separator like ``&&`` /
    ``||`` / ``;`` / ``|``, must not flip the enforcer into the
    browser-flow no-op path. A ``-w`` sitting inside a quoted argument
    (for example ``--body "see -w docs"``) likewise must not match.

    Args:
        command: Raw bash command string from PreToolUse hook input.

    Returns:
        True when ``--web`` or ``-w`` appears as a whole token between
        the ``gh pr create`` match and the next shell command separator
        (or end of string), with quoted regions stripped before the
        scan. Substrings like ``--webhook`` are not matched. False when
        ``gh pr create`` is absent or the flag falls outside its
        segment.
    """
    quote_stripped_command = _strip_quoted_regions(command)
    gh_pr_create_match = GH_PR_CREATE_PATTERN.search(quote_stripped_command)
    if gh_pr_create_match is None:
        return False
    segment_start = gh_pr_create_match.end()
    separator_match = COMMAND_SEPARATOR_PATTERN.search(quote_stripped_command, segment_start)
    segment_end = separator_match.start() if separator_match else len(quote_stripped_command)
    gh_pr_create_segment = quote_stripped_command[segment_start:segment_end]
    return bool(WEB_FLAG_PATTERN.search(gh_pr_create_segment))


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
