"""Canonical-location tests for the gh-pr-author swap utils module.

The TDD enforcer matches a production filename ``X.py`` to ``test_X.py``;
``_gh_pr_author_swap_utils.py`` carries a leading underscore that the
enforcer treats as part of the name. This file's tests are the canonical
match. The broader behavioural suite lives alongside in
``blocking/test_gh_pr_author_swap_utils.py``.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import tempfile

import pytest

from config.gh_pr_author_swap_constants import STATE_FILE_PERMISSION_MODE

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

utils_module_spec = importlib.util.spec_from_file_location(
    "_gh_pr_author_swap_utils",
    _HOOKS_ROOT / "_gh_pr_author_swap_utils.py",
)
assert utils_module_spec is not None
assert utils_module_spec.loader is not None
utils_module = importlib.util.module_from_spec(utils_module_spec)
utils_module_spec.loader.exec_module(utils_module)


def test_state_file_path_rejects_path_traversal_session_id() -> None:
    """A session_id containing path-traversal characters must not escape tempdir.

    Regression guard: an unsanitised ``session_id`` containing ``../`` or
    ``/`` would interpolate into the filename and let the resulting path
    land outside ``tempfile.gettempdir()``. The sanitiser strips every
    character outside ``[A-Za-z0-9_-]`` and falls back to the default
    session id when the result is empty.
    """
    sanitised_path = utils_module._state_file_path("../../tmp/evil")
    temporary_directory_path = pathlib.Path(tempfile.gettempdir()).resolve()
    assert sanitised_path.parent.resolve() == temporary_directory_path


def test_state_file_path_rejects_backslash_in_session_id() -> None:
    """Backslashes are also unsafe path separators on Windows."""
    sanitised_path = utils_module._state_file_path("evil\\..\\..\\system32")
    temporary_directory_path = pathlib.Path(tempfile.gettempdir()).resolve()
    assert sanitised_path.parent.resolve() == temporary_directory_path


def test_state_file_path_rejects_nul_byte_in_session_id() -> None:
    """A NUL byte inside the session id must not reach the filename."""
    sanitised_path = utils_module._state_file_path("abc\x00../def")
    temporary_directory_path = pathlib.Path(tempfile.gettempdir()).resolve()
    assert sanitised_path.parent.resolve() == temporary_directory_path
    assert "\x00" not in sanitised_path.name


def test_state_file_path_preserves_safe_session_id() -> None:
    """A well-formed session id passes through unchanged."""
    safe_session_id = "session-001_abc"
    produced_path = utils_module._state_file_path(safe_session_id)
    assert safe_session_id in produced_path.name


def test_backtick_substitution_blanks_inner_quoted_literals() -> None:
    """A ``gh pr create`` literal inside a single-quoted argument of a backtick body must not trigger.

    Mirrors ``$(printf '...')`` behaviour: when the backtick body's
    quoted literal contains the token, the matcher must blank the
    quoted region before searching.
    """
    stripped_command = utils_module._strip_quoted_regions("foo `printf ';gh pr create'`")
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(stripped_command)


def test_backtick_substitution_matches_unquoted_gh_pr_create_inside_body() -> None:
    """A bare ``gh pr create`` inside a backtick body still matches.

    Symmetric to ``$(gh pr create)`` — the substitution body is real
    code, so the matcher must see it.
    """
    stripped_command = utils_module._strip_quoted_regions("echo `gh pr create --title T`")
    assert utils_module._command_invokes_gh_pr_create_in_stripped(stripped_command)


def test_state_file_is_attacker_planted_returns_true_for_world_readable_mode(
    tmp_path: pathlib.Path,
) -> None:
    """A state file with mode 0o644 is flagged as attacker-planted on POSIX.

    The enforcer always atomically creates state files at 0o600. A file
    at the predictable swap-state path with any other mode bits cannot
    have come from the enforcer running as this user.
    """
    if not hasattr(os, "getuid"):
        return
    state_file = tmp_path / "gh_pr_author_swap_session-attacker.json"
    state_file.write_text("{}", encoding="utf-8")
    os.chmod(state_file, 0o644)

    assert utils_module._state_file_is_attacker_planted(state_file) is True


def test_state_file_is_attacker_planted_returns_false_for_well_formed_file(
    tmp_path: pathlib.Path,
) -> None:
    """A state file written exactly the way the enforcer writes is not flagged."""
    state_file = tmp_path / "gh_pr_author_swap_session-good.json"
    state_file.write_text("{}", encoding="utf-8")
    if hasattr(os, "getuid"):
        os.chmod(state_file, STATE_FILE_PERMISSION_MODE)

    assert utils_module._state_file_is_attacker_planted(state_file) is False


def test_state_file_is_attacker_planted_returns_false_for_missing_file(
    tmp_path: pathlib.Path,
) -> None:
    """A missing state file is treated as not-planted so callers can no-op cleanly."""
    missing_state_file = tmp_path / "gh_pr_author_swap_session-missing.json"

    assert utils_module._state_file_is_attacker_planted(missing_state_file) is False
