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
    COMMAND_SEPARATOR_PATTERN,
    COMMAND_SUBSTITUTION_OPENER_LENGTH,
    GH_AUTH_SWITCH_TIMEOUT_SECONDS,
    GH_PR_CREATE_PATTERN,
    SHELL_BACKSLASH_ESCAPE_PAIR_LENGTH,
    SHELL_BACKTICK_CHARACTER,
    SHELL_DOLLAR_CHARACTER,
    SHELL_PAREN_CLOSE_CHARACTER,
    SHELL_PAREN_OPEN_CHARACTER,
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


def _index_after_command_substitution(all_scanned_characters: list[str], opener_index: int) -> int:
    """Return the index one past the closing ``)`` of a ``$(...)`` substitution.

    Walks from the opening ``$(`` past nested ``$(...)`` substitutions
    and skips past inner quoted regions and backtick substitutions so the
    closing paren matched is the one that actually balances the opener.
    Bash executes the substitution body, so the interior characters are
    left untouched — callers must still see any ``gh pr create`` token
    sitting inside.

    Quote handling mirrors ``_strip_quoted_regions``:

    * A single-quoted region (``'...'``) has no escape mechanism in bash —
      the walker advances to the next ``'`` and resumes paren scanning.
    * A double-quoted region (``"..."``) honors backslash escapes — a
      ``\\`` followed by any character is consumed as a two-character
      unit, so ``\\"`` does not terminate the region.
    * A backtick substitution (``` `...` ```) inside the ``$(...)`` body
      is itself a subshell — the walker advances past the next backtick
      so that a ``)`` sitting inside the backtick body does not flip the
      surrounding paren depth.

    Unterminated quotes and backticks consume to the end of the buffer,
    matching the behavior of ``_strip_quoted_regions``.

    Args:
        all_scanned_characters: Mutable list view of the command string.
            The walker reads but does not write — interior characters of
            the substitution body remain intact for downstream matching.
        opener_index: Index of the ``$`` that begins ``$(``.

    Returns:
        The index just past the matching ``)``. When no closing paren is
        found the length of the buffer is returned, matching how an
        interactive shell would consume the rest of the input on an
        unterminated substitution.
    """
    paren_depth = 1
    interior_index = opener_index + COMMAND_SUBSTITUTION_OPENER_LENGTH
    buffer_length = len(all_scanned_characters)
    while interior_index < buffer_length and paren_depth > 0:
        interior_character = all_scanned_characters[interior_index]
        if (
            interior_character == SHELL_DOLLAR_CHARACTER
            and interior_index + 1 < buffer_length
            and all_scanned_characters[interior_index + 1] == SHELL_PAREN_OPEN_CHARACTER
        ):
            paren_depth += 1
            interior_index += COMMAND_SUBSTITUTION_OPENER_LENGTH
            continue
        if interior_character == SHELL_BACKTICK_CHARACTER:
            interior_index = _index_after_backtick_substitution(
                all_scanned_characters, interior_index, buffer_length
            )
            continue
        if interior_character in ALL_SHELL_QUOTE_CHARACTERS:
            interior_index = _index_after_quoted_region(
                all_scanned_characters, interior_index, buffer_length, interior_character
            )
            continue
        if interior_character == SHELL_PAREN_CLOSE_CHARACTER:
            paren_depth -= 1
            interior_index += 1
            continue
        interior_index += 1
    return interior_index


def _index_after_backtick_substitution(
    all_scanned_characters: list[str],
    opener_index: int,
    buffer_length: int,
) -> int:
    """Return the index one past the closing backtick of a ``` `...` ``` region.

    Args:
        all_scanned_characters: Mutable list view of the command string.
        opener_index: Index of the opening backtick.
        buffer_length: Length of ``all_scanned_characters``, hoisted by
            the caller to avoid a recomputation per call.

    Returns:
        The index just past the matching backtick, or ``buffer_length``
        when the backtick region is unterminated.
    """
    interior_index = opener_index + 1
    while interior_index < buffer_length:
        if all_scanned_characters[interior_index] == SHELL_BACKTICK_CHARACTER:
            return interior_index + 1
        interior_index += 1
    return interior_index


def _index_after_quoted_region(
    all_scanned_characters: list[str],
    opener_index: int,
    buffer_length: int,
    quote_character: str,
) -> int:
    """Return the index one past the matching quote of a ``'...'`` or ``"..."`` region.

    Single quotes have no escape mechanism in bash, so the walker advances
    to the next matching ``'``. Double quotes honor ``\\`` escapes, so a
    ``\\`` followed by any character is consumed as a two-character unit
    (``\\"`` does not terminate the region).

    Args:
        all_scanned_characters: Mutable list view of the command string.
        opener_index: Index of the opening quote.
        buffer_length: Length of ``all_scanned_characters``, hoisted by
            the caller to avoid a recomputation per call.
        quote_character: ``'`` or ``"`` — the quote whose match closes
            the region.

    Returns:
        The index just past the matching closing quote, or ``buffer_length``
        when the quoted region is unterminated.
    """
    interior_index = opener_index + 1
    while interior_index < buffer_length:
        interior_character = all_scanned_characters[interior_index]
        if (
            quote_character == '"'
            and interior_character == "\\"
            and interior_index + 1 < buffer_length
        ):
            interior_index += SHELL_BACKSLASH_ESCAPE_PAIR_LENGTH
            continue
        if interior_character == quote_character:
            return interior_index + 1
        interior_index += 1
    return interior_index


def _strip_quoted_regions(command: str) -> str:
    """Replace inert quoted regions with spaces, leaving substitutions scannable.

    Single quotes (``'...'``) and double quotes (``"..."``) wrap inert
    text in bash, so their interior is replaced with spaces. ``$(...)``
    command substitution and backtick command substitution
    (``` `...` ```) execute their bodies in a subshell, so the interior
    is left intact — any ``gh pr create`` token sitting inside either
    form must remain visible to the matchers, otherwise the enforcer
    would silently no-op on ``echo "$(gh pr create --title T)"``.

    Within a double-quoted region, ``$(...)`` substitution windows are
    still expanded, so the walker recognizes the ``$(`` opener inside
    the quoted scan and stops stripping until the matching ``)`` —
    leaving the substitution body scannable while keeping the surrounding
    quoted text inert. Backtick command substitution (``` `...` ```) is
    likewise expanded by bash inside double quotes, so the same
    skip-past-body behavior applies: the walker advances past the closing
    backtick without stripping the interior, so any ``gh pr create`` token
    sitting inside ``"`...`"`` remains visible to the matcher.

    Backslash-escaped quotes inside a double-quoted segment (``\\"``) do
    not terminate the region. An unterminated quote consumes the rest of
    the string, matching how an interactive shell parses the same input.

    Args:
        command: Raw bash command string from PreToolUse hook input.

    Returns:
        A string of identical length to ``command`` with single- and
        double-quoted region interiors replaced by spaces, and the
        bodies of ``$(...)`` / ``` `...` ``` substitutions left intact.
    """
    all_scanned_characters = list(command)
    cursor_index = 0
    command_length = len(command)
    while cursor_index < command_length:
        current_character = all_scanned_characters[cursor_index]
        if (
            current_character == SHELL_DOLLAR_CHARACTER
            and cursor_index + 1 < command_length
            and all_scanned_characters[cursor_index + 1] == SHELL_PAREN_OPEN_CHARACTER
        ):
            cursor_index = _index_after_command_substitution(all_scanned_characters, cursor_index)
            continue
        if current_character == SHELL_BACKTICK_CHARACTER:
            interior_index = cursor_index + 1
            while interior_index < command_length:
                if all_scanned_characters[interior_index] == SHELL_BACKTICK_CHARACTER:
                    interior_index += 1
                    break
                interior_index += 1
            cursor_index = interior_index
            continue
        if current_character not in ALL_SHELL_QUOTE_CHARACTERS:
            cursor_index += 1
            continue
        quote_character = current_character
        all_scanned_characters[cursor_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
        interior_index = cursor_index + 1
        while interior_index < command_length:
            interior_character = all_scanned_characters[interior_index]
            if (
                quote_character == '"'
                and interior_character == "\\"
                and interior_index + 1 < command_length
            ):
                all_scanned_characters[interior_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
                all_scanned_characters[interior_index + 1] = SHELL_QUOTE_REPLACEMENT_CHARACTER
                interior_index += SHELL_BACKSLASH_ESCAPE_PAIR_LENGTH
                continue
            if (
                quote_character == '"'
                and interior_character == SHELL_DOLLAR_CHARACTER
                and interior_index + 1 < command_length
                and all_scanned_characters[interior_index + 1] == SHELL_PAREN_OPEN_CHARACTER
            ):
                interior_index = _index_after_command_substitution(all_scanned_characters, interior_index)
                continue
            if quote_character == '"' and interior_character == SHELL_BACKTICK_CHARACTER:
                interior_index += 1
                while interior_index < command_length:
                    if all_scanned_characters[interior_index] == SHELL_BACKTICK_CHARACTER:
                        interior_index += 1
                        break
                    interior_index += 1
                continue
            if interior_character == quote_character:
                all_scanned_characters[interior_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
                interior_index += 1
                break
            all_scanned_characters[interior_index] = SHELL_QUOTE_REPLACEMENT_CHARACTER
            interior_index += 1
        cursor_index = interior_index
    return "".join(all_scanned_characters)


def _all_gh_pr_create_segments(quote_stripped_command: str) -> list[str]:
    """Return every ``gh pr create`` segment in the (quote-stripped) command.

    A "segment" is the substring from the end of a ``gh pr create`` match
    up to the next shell command separator (``&&``, ``||``, ``;``,
    ``|``, ``&``, newline) or the end of the string. The enforcer's
    web-flag detection runs against each segment independently so a
    chained ``gh pr create --web && gh pr create --title T`` does not
    let the second invocation slip through on the strength of the
    first segment's ``--web`` flag.

    Args:
        quote_stripped_command: Output of ``_strip_quoted_regions`` —
            the caller is responsible for stripping inert quoted regions
            before passing in.

    Returns:
        List of segment strings, one per ``gh pr create`` invocation
        found in the command. Empty list when the command does not
        invoke ``gh pr create`` at all.
    """
    all_segments: list[str] = []
    command_length = len(quote_stripped_command)
    for each_gh_pr_create_match in GH_PR_CREATE_PATTERN.finditer(quote_stripped_command):
        segment_start = each_gh_pr_create_match.end()
        separator_match = COMMAND_SEPARATOR_PATTERN.search(quote_stripped_command, segment_start)
        segment_end = separator_match.start() if separator_match else command_length
        all_segments.append(quote_stripped_command[segment_start:segment_end])
    return all_segments


def _command_invokes_gh_pr_create_in_stripped(quote_stripped_command: str) -> bool:
    """Return True when the (quote-stripped) command contains a ``gh pr create`` invocation.

    Both the enforcer's PreToolUse gate and the restore hook's
    PostToolUse gate share this function, so the pair stays in sync —
    a fix here lands on both ends of the swap-restore pair at once.
    A literal ``gh pr create`` inside ``echo "..."`` or any other quoted
    argument is intentionally ignored because the caller has already run
    ``_strip_quoted_regions`` to blank out inert quoted text.

    Args:
        quote_stripped_command: Output of ``_strip_quoted_regions`` —
            the caller is responsible for stripping inert quoted regions
            before passing in. ``main()`` in the enforcer computes this
            once and passes it to both this helper and
            ``_command_uses_web_flag_in_stripped`` so the character-walk
            in ``_strip_quoted_regions`` runs exactly once per command.

    Returns:
        True when ``gh pr create`` appears as a whole-word match in the
        already-stripped command. Matches regardless of whether ``gh``
        is at the start of the command or embedded in a chained pipeline.
    """
    return bool(GH_PR_CREATE_PATTERN.search(quote_stripped_command))
