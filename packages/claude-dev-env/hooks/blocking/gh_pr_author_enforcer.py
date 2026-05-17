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
import tempfile
from pathlib import Path
from typing import TextIO

from config.gh_pr_author_swap_constants import (
    ALL_GH_API_USER_COMMAND,
    ALL_GH_AUTH_SWITCH_COMMAND_HEAD,
    BASH_TOOL_NAME,
    COMMAND_SEPARATOR_PATTERN,
    GH_API_USER_TIMEOUT_SECONDS,
    GH_AUTH_SWITCH_TIMEOUT_SECONDS,
    GH_PR_CREATE_PATTERN,
    REQUIRED_ACCOUNT_ENV_VAR,
    STATE_FILE_DEFAULT_SESSION_ID,
    STATE_FILE_ORIGINAL_ACCOUNT_KEY,
    STATE_FILE_PREFIX,
    STATE_FILE_PRIMARY_ACCOUNT_KEY,
    STATE_FILE_SUFFIX,
    WEB_FLAG_PATTERN,
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


def _switch_gh_account(to_account: str) -> bool:
    """Run ``gh auth switch --user <to_account>`` and report success.

    Args:
        to_account: Login to switch the active gh CLI account to.

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
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
    return completed_process.returncode == 0


def _state_file_path(session_id: str) -> Path:
    """Return the per-session state-file path used to hand off to the restore hook.

    Args:
        session_id: ``session_id`` from the Claude Code hook input JSON.
            Empty string falls back to ``STATE_FILE_DEFAULT_SESSION_ID``.

    Returns:
        Absolute path to the state file in the system temp directory.
    """
    effective_session_id = session_id or STATE_FILE_DEFAULT_SESSION_ID
    filename = f"{STATE_FILE_PREFIX}{effective_session_id}{STATE_FILE_SUFFIX}"
    return Path(tempfile.gettempdir()) / filename


def _write_swap_state(
    state_file: Path,
    original_account: str,
    primary_account: str,
) -> bool:
    """Persist the swap-back state for the PostToolUse restore hook.

    Args:
        state_file: Destination path returned by ``_state_file_path``.
        original_account: Login that was active before the swap.
        primary_account: Login swapped to (always ``GITHUB_DEFAULT_ACCOUNT``).

    Returns:
        True when the write succeeds. False on any filesystem failure.
    """
    swap_state = {
        STATE_FILE_ORIGINAL_ACCOUNT_KEY: original_account,
        STATE_FILE_PRIMARY_ACCOUNT_KEY: primary_account,
    }
    try:
        state_file.write_text(json.dumps(swap_state), encoding="utf-8")
    except OSError:
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


def _command_invokes_gh_pr_create(command: str) -> bool:
    """Return True when the command string contains a ``gh pr create`` invocation.

    Args:
        command: Raw bash command string from PreToolUse hook input.

    Returns:
        True when ``gh pr create`` appears as a whole-word match. Matches
        regardless of whether ``gh`` is at the start of the command or
        embedded in a chained pipeline.
    """
    return bool(GH_PR_CREATE_PATTERN.search(command))


def _command_uses_web_flag(command: str) -> bool:
    """Return True when ``--web`` / ``-w`` appears inside the ``gh pr create`` segment.

    The flag is only relevant when it modifies the ``gh pr create``
    invocation itself. A ``-w`` token belonging to an unrelated command
    (for example ``curl -w '%{http_code}'``) before ``gh pr create``, or
    a flag attached to a chained command after a separator like ``&&`` /
    ``||`` / ``;`` / ``|``, must not flip the enforcer into the
    browser-flow no-op path.

    Args:
        command: Raw bash command string from PreToolUse hook input.

    Returns:
        True when ``--web`` or ``-w`` appears as a whole token between
        the ``gh pr create`` match and the next shell command separator
        (or end of string). Substrings like ``--webhook`` are not
        matched. False when ``gh pr create`` is absent or the flag falls
        outside its segment.
    """
    gh_pr_create_match = GH_PR_CREATE_PATTERN.search(command)
    if gh_pr_create_match is None:
        return False
    segment_start = gh_pr_create_match.end()
    separator_match = COMMAND_SEPARATOR_PATTERN.search(command, segment_start)
    segment_end = separator_match.start() if separator_match else len(command)
    gh_pr_create_segment = command[segment_start:segment_end]
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

    switch_succeeded = _switch_gh_account(required_account)
    if not switch_succeeded:
        _emit_deny_payload(
            _build_switch_failure_message(required_account, current_account)
        )
        sys.exit(0)

    session_id = str(hook_input.get("session_id") or "")
    state_file = _state_file_path(session_id)
    state_write_succeeded = _write_swap_state(
        state_file,
        original_account=current_account,
        primary_account=required_account,
    )
    if not state_write_succeeded:
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
