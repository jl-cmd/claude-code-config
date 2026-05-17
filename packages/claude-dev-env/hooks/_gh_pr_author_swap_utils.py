"""Shared utilities for the gh-pr-author swap hook trio.

The PreToolUse enforcer (``hooks/blocking/gh_pr_author_enforcer.py``), the
PostToolUse restore (``hooks/blocking/gh_pr_author_restore.py``), and the
SessionStart cleanup (``hooks/session/gh_pr_author_session_cleanup.py``)
all need a small overlapping set of helpers: write a line to a stream,
build the per-session state-file path, run ``gh auth switch``, read the
original-account login from a state file, delete a state file, and
detect a ``gh pr create`` invocation while ignoring quoted regions.

Pulling these into one module fixes two related defects in one step:

1. A bug fix applied to one copy of a helper used to require remembering
   to apply it to the other two. The previous round shipped a regression
   where the enforcer's ``_command_invokes_gh_pr_create`` was updated to
   strip quoted regions but the restore hook's copy was missed.
2. The hook trio shares stable state-file shape and gh subprocess
   contracts. Centralizing those contracts removes the temptation to
   let the copies drift apart on future edits.

This module follows the precedent set by ``_gh_body_arg_utils.py`` in
``hooks/blocking/`` — leading underscore marks it as internal to the
feature, and the file lives directly under ``hooks/`` so both
``hooks/blocking/`` and ``hooks/session/`` consumers can import it
without a per-directory path shim.
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
    ALL_SHELL_QUOTE_CHARACTERS,
    GH_AUTH_SWITCH_TIMEOUT_SECONDS,
    GH_PR_CREATE_PATTERN,
    SHELL_BACKSLASH_ESCAPE_PAIR_LENGTH,
    SHELL_QUOTE_REPLACEMENT_CHARACTER,
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
            Each caller formats its own prefix into ``message``.
    """
    output_stream.write(message + "\n")
    output_stream.flush()


def _state_file_path(session_id: str) -> Path:
    """Return the per-session state-file path used by the hook trio.

    The enforcer writes the file, the restore hook reads and deletes it,
    and the session-cleanup hook globs the prefix to recover stranded
    files. All three share this naming convention so a state file
    written by one hook is always resolvable by the others.

    Args:
        session_id: ``session_id`` from the Claude Code hook input JSON.
            Empty string falls back to ``STATE_FILE_DEFAULT_SESSION_ID``.

    Returns:
        Absolute path to the state file in the system temp directory.
    """
    effective_session_id = session_id or STATE_FILE_DEFAULT_SESSION_ID
    filename = f"{STATE_FILE_PREFIX}{effective_session_id}{STATE_FILE_SUFFIX}"
    return Path(tempfile.gettempdir()) / filename


def _switch_gh_account(to_account: str) -> bool:
    """Run ``gh auth switch --user <to_account>`` and report success.

    Diagnostics on failure are intentionally not written here. Callers
    decide whether a failed switch is worth a stderr line (the restore
    and cleanup hooks log; the enforcer suppresses to keep the deny-path
    payload the only output on the failure branch).

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


def _read_original_account(state_file: Path) -> str | None:
    """Read the original-account login from a swap-state file.

    Args:
        state_file: Path produced by ``_state_file_path``.

    Returns:
        The original account login when the file exists and parses to a
        JSON object with a non-empty string ``original_account`` value.
        None when the file is absent, unreadable, malformed JSON, the
        wrong shape, missing the key, holds a non-string value, or holds
        a blank value. Diagnostics for unreadable or malformed files are
        written to stderr so the caller can see why a state file was not
        consumed.
    """
    try:
        raw_contents = state_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as os_error:
        _write_line(
            f"[gh-pr-author-utils] failed to read state file {state_file}: {os_error}",
            sys.stderr,
        )
        return None
    try:
        parsed_state = json.loads(raw_contents)
    except json.JSONDecodeError as decode_error:
        _write_line(
            f"[gh-pr-author-utils] malformed state file {state_file}: {decode_error}",
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
    """Remove a state file, ignoring an already-absent file.

    Args:
        state_file: Path produced by ``_state_file_path``.
    """
    try:
        state_file.unlink()
    except FileNotFoundError:
        return
    except OSError as os_error:
        _write_line(
            f"[gh-pr-author-utils] failed to delete state file {state_file}: {os_error}",
            sys.stderr,
        )


def _strip_quoted_regions(command: str) -> str:
    """Replace double-quoted, single-quoted, and backtick-quoted regions with spaces.

    The enforcer's matchers (``GH_PR_CREATE_PATTERN``,
    ``WEB_FLAG_PATTERN``, ``COMMAND_SEPARATOR_PATTERN``) operate on the
    raw command string. Without quote-stripping, a literal ``gh pr create``
    or a ``-w`` token sitting inside a ``--body "..."`` argument would
    false-positive into the matchers. Replacing each quoted region with
    spaces of equal length preserves every offset so callers can keep
    indexing the original command's match positions, while making the
    quoted text inert to the regex search.

    Backslash-escaped quotes inside a quoted region (``\\"`` inside a
    double-quoted segment, ``\\'`` inside a single-quoted segment) do not
    terminate the region. An unterminated quote consumes the rest of the
    string; this matches how an interactive shell would parse the same
    input and keeps the matchers from seeing tokens past a syntactically
    broken command.

    Args:
        command: Raw bash command string from PreToolUse hook input.

    Returns:
        A string of identical length to ``command`` with every quoted
        region's interior replaced by spaces. The quote characters
        themselves are also replaced with spaces so a stray ``--body
        "gh pr create"`` does not look like an invocation.
    """
    scanned_characters = list(command)
    cursor_index = 0
    command_length = len(command)
    while cursor_index < command_length:
        current_character = scanned_characters[cursor_index]
        if current_character not in ALL_SHELL_QUOTE_CHARACTERS:
            cursor_index += 1
            continue
        quote_character = current_character
        scanned_characters[cursor_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
        interior_index = cursor_index + 1
        while interior_index < command_length:
            interior_character = scanned_characters[interior_index]
            if (
                quote_character == '"'
                and interior_character == "\\"
                and interior_index + 1 < command_length
            ):
                scanned_characters[interior_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
                scanned_characters[interior_index + 1] = SHELL_QUOTE_REPLACEMENT_CHARACTER
                interior_index += SHELL_BACKSLASH_ESCAPE_PAIR_LENGTH
                continue
            if interior_character == quote_character:
                scanned_characters[interior_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
                interior_index += 1
                break
            scanned_characters[interior_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
            interior_index += 1
        cursor_index = interior_index
    return "".join(scanned_characters)


def _command_invokes_gh_pr_create(command: str) -> bool:
    """Return True when the command string contains a ``gh pr create`` invocation.

    Strips quoted regions before searching so a literal ``gh pr create``
    inside ``echo "..."`` or any other quoted argument is intentionally
    ignored. Both the enforcer's PreToolUse gate and the restore hook's
    PostToolUse gate share this function, so the pair stays in sync —
    a fix here lands on both ends of the swap-restore pair at once.

    Args:
        command: Raw bash command string from PreToolUse / PostToolUse
            hook input.

    Returns:
        True when ``gh pr create`` appears as a whole-word match outside
        any quoted region. Matches regardless of whether ``gh`` is at the
        start of the command or embedded in a chained pipeline.
    """
    quote_stripped_command = _strip_quoted_regions(command)
    return bool(GH_PR_CREATE_PATTERN.search(quote_stripped_command))
