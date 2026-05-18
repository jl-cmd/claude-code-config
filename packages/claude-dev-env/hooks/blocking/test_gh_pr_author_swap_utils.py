"""Unit tests for the shared gh-pr-author swap utils module."""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys
from typing import Iterator
from unittest import mock

import pytest

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
for each_sys_path_entry in (str(_HOOKS_ROOT), str(_HOOKS_ROOT / "blocking")):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

utils_module_spec = importlib.util.spec_from_file_location(
    "_gh_pr_author_swap_utils",
    _HOOKS_ROOT / "_gh_pr_author_swap_utils.py",
)
assert utils_module_spec is not None
assert utils_module_spec.loader is not None
utils_module = importlib.util.module_from_spec(utils_module_spec)
utils_module_spec.loader.exec_module(utils_module)


@pytest.fixture
def isolated_temp_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> Iterator[pathlib.Path]:
    monkeypatch.setattr(utils_module.tempfile, "gettempdir", lambda: str(tmp_path))
    yield tmp_path


def test_strip_quoted_regions_preserves_offsets_for_double_quotes() -> None:
    original_command = 'gh pr create --body "some text" --title T'
    stripped_command = utils_module._strip_quoted_regions(original_command)
    assert len(stripped_command) == len(original_command)
    assert "some text" not in stripped_command
    assert "gh pr create" in stripped_command
    assert "--title T" in stripped_command


def test_strip_quoted_regions_preserves_offsets_for_single_quotes() -> None:
    original_command = "gh pr create --body 'single quoted body' --title T"
    stripped_command = utils_module._strip_quoted_regions(original_command)
    assert len(stripped_command) == len(original_command)
    assert "single quoted body" not in stripped_command


def test_strip_quoted_regions_preserves_backtick_substitution_body() -> None:
    """Backticks delimit command substitution, which executes — the body must remain scannable."""
    original_command = "echo `inner cmd` && gh pr create --title T"
    stripped_command = utils_module._strip_quoted_regions(original_command)
    assert len(stripped_command) == len(original_command)
    assert "inner cmd" in stripped_command
    assert "gh pr create" in stripped_command


def test_strip_quoted_regions_preserves_dollar_paren_substitution_body() -> None:
    """``$(...)`` substitution body must remain scannable for the same reason as backticks."""
    original_command = "echo $(inner cmd) && gh pr create --title T"
    stripped_command = utils_module._strip_quoted_regions(original_command)
    assert len(stripped_command) == len(original_command)
    assert "inner cmd" in stripped_command
    assert "gh pr create" in stripped_command


def test_strip_quoted_regions_preserves_dollar_paren_inside_double_quotes() -> None:
    """``"$(...)"`` substitution body remains scannable even when wrapped in double quotes."""
    original_command = 'echo "$(inner cmd)" && gh pr create --title T'
    stripped_command = utils_module._strip_quoted_regions(original_command)
    assert len(stripped_command) == len(original_command)
    assert "inner cmd" in stripped_command
    assert "gh pr create" in stripped_command


def test_strip_quoted_regions_handles_escaped_quote_inside_double_quotes() -> None:
    original_command = 'gh pr create --body "escaped \\" quote" --title T'
    stripped_command = utils_module._strip_quoted_regions(original_command)
    assert len(stripped_command) == len(original_command)
    assert "escaped" not in stripped_command
    assert "--title T" in stripped_command


def test_strip_quoted_regions_returns_empty_for_empty_input() -> None:
    assert utils_module._strip_quoted_regions("") == ""


def test_strip_quoted_regions_leaves_unquoted_command_unchanged() -> None:
    unquoted_command = "gh pr create --title T --body-file body.md"
    assert utils_module._strip_quoted_regions(unquoted_command) == unquoted_command


def test_strip_quoted_regions_handles_unterminated_quote_to_end() -> None:
    unterminated_command = 'gh pr create --body "never closed gh pr create'
    stripped_command = utils_module._strip_quoted_regions(unterminated_command)
    assert len(stripped_command) == len(unterminated_command)
    assert "never closed" not in stripped_command


def test_command_invokes_gh_pr_create_matches_basic_form() -> None:
    assert utils_module._command_invokes_gh_pr_create("gh pr create --title T")


def test_command_invokes_gh_pr_create_matches_chained_form() -> None:
    assert utils_module._command_invokes_gh_pr_create("git push && gh pr create")


def test_command_invokes_gh_pr_create_rejects_pr_edit() -> None:
    assert not utils_module._command_invokes_gh_pr_create("gh pr edit 10 --title X")


def test_command_invokes_gh_pr_create_rejects_substring() -> None:
    assert not utils_module._command_invokes_gh_pr_create("some-gh pr created-by")


def test_command_invokes_gh_pr_create_ignores_literal_inside_double_quotes() -> None:
    assert not utils_module._command_invokes_gh_pr_create('echo "gh pr create docs"')


def test_command_invokes_gh_pr_create_ignores_literal_inside_single_quotes() -> None:
    assert not utils_module._command_invokes_gh_pr_create("echo 'gh pr create docs'")


def test_command_invokes_gh_pr_create_detects_backtick_substitution_body() -> None:
    """Backtick substitution body executes, so an inner ``gh pr create`` is real."""
    assert utils_module._command_invokes_gh_pr_create("echo `gh pr create docs`")


def test_command_invokes_gh_pr_create_detects_dollar_paren_substitution_body() -> None:
    """``$(...)`` substitution body executes, so an inner ``gh pr create`` is real."""
    assert utils_module._command_invokes_gh_pr_create('echo "$(gh pr create docs)"')


def test_command_invokes_gh_pr_create_still_matches_unquoted_invocation() -> None:
    assert utils_module._command_invokes_gh_pr_create(
        'gh pr create --body "see docs about gh pr create"'
    )


def test_state_file_path_uses_session_id(
    isolated_temp_directory: pathlib.Path,
) -> None:
    state_file = utils_module._state_file_path("abc-123")
    assert state_file.parent == isolated_temp_directory
    assert state_file.name == "gh_pr_author_swap_abc-123.json"


def test_state_file_path_falls_back_to_default_when_session_id_empty(
    isolated_temp_directory: pathlib.Path,
) -> None:
    state_file = utils_module._state_file_path("")
    assert state_file.parent == isolated_temp_directory
    assert state_file.name == "gh_pr_author_swap_default.json"


def test_state_file_path_includes_default_for_falsy_input(
    isolated_temp_directory: pathlib.Path,
) -> None:
    state_file_for_empty_string = utils_module._state_file_path("")
    assert "default" in state_file_for_empty_string.name


def test_switch_gh_account_returns_true_on_success() -> None:
    completed = mock.Mock(returncode=0, stdout="", stderr="")
    with mock.patch.object(utils_module.subprocess, "run", return_value=completed):
        assert utils_module._switch_gh_account("JonEcho") is True


def test_switch_gh_account_returns_false_on_nonzero_exit() -> None:
    completed = mock.Mock(returncode=1, stdout="", stderr="boom")
    with mock.patch.object(utils_module.subprocess, "run", return_value=completed):
        assert utils_module._switch_gh_account("JonEcho") is False


def test_switch_gh_account_returns_false_when_gh_missing() -> None:
    with mock.patch.object(utils_module.subprocess, "run", side_effect=FileNotFoundError):
        assert utils_module._switch_gh_account("JonEcho") is False


def test_switch_gh_account_returns_false_on_timeout() -> None:
    with mock.patch.object(
        utils_module.subprocess,
        "run",
        side_effect=utils_module.subprocess.TimeoutExpired(cmd="gh", timeout=10),
    ):
        assert utils_module._switch_gh_account("JonEcho") is False


def test_read_original_account_returns_login_for_well_formed_file(
    isolated_temp_directory: pathlib.Path,
) -> None:
    state_file = isolated_temp_directory / "well_formed.json"
    state_file.write_text(
        json.dumps({"original_account": "jl-cmd", "primary_account": "JonEcho"}),
        encoding="utf-8",
    )
    assert utils_module._read_original_account(state_file) == "jl-cmd"


def test_read_original_account_returns_none_for_missing_file(
    isolated_temp_directory: pathlib.Path,
) -> None:
    missing_file = isolated_temp_directory / "does_not_exist.json"
    assert utils_module._read_original_account(missing_file) is None


def test_read_original_account_returns_none_for_non_dict_payload(
    isolated_temp_directory: pathlib.Path,
) -> None:
    list_payload_file = isolated_temp_directory / "list_payload.json"
    list_payload_file.write_text(json.dumps(["jl-cmd"]), encoding="utf-8")
    assert utils_module._read_original_account(list_payload_file) is None


def test_read_original_account_returns_none_for_non_string_value(
    isolated_temp_directory: pathlib.Path,
) -> None:
    bad_type_file = isolated_temp_directory / "bad_type.json"
    bad_type_file.write_text(json.dumps({"original_account": 42}), encoding="utf-8")
    assert utils_module._read_original_account(bad_type_file) is None


def test_read_original_account_returns_none_for_blank_value(
    isolated_temp_directory: pathlib.Path,
) -> None:
    blank_value_file = isolated_temp_directory / "blank.json"
    blank_value_file.write_text(json.dumps({"original_account": "   "}), encoding="utf-8")
    assert utils_module._read_original_account(blank_value_file) is None


def test_read_original_account_returns_none_for_malformed_json(
    isolated_temp_directory: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", captured_stderr)
    malformed_file = isolated_temp_directory / "malformed.json"
    malformed_file.write_text("{not valid json", encoding="utf-8")
    assert utils_module._read_original_account(malformed_file) is None


def test_delete_state_file_is_silent_when_already_absent(
    isolated_temp_directory: pathlib.Path,
) -> None:
    missing_file = isolated_temp_directory / "does_not_exist.json"
    utils_module._delete_state_file(missing_file)
    assert not missing_file.exists()


def test_delete_state_file_removes_existing_file(
    isolated_temp_directory: pathlib.Path,
) -> None:
    existing_file = isolated_temp_directory / "to_remove.json"
    existing_file.write_text("payload", encoding="utf-8")
    assert existing_file.exists()
    utils_module._delete_state_file(existing_file)
    assert not existing_file.exists()


def test_write_line_appends_newline_and_flushes() -> None:
    captured_stream = io.StringIO()
    utils_module._write_line("hello", captured_stream)
    assert captured_stream.getvalue() == "hello\n"


def test_write_line_writes_multiple_lines_in_call_order() -> None:
    captured_stream = io.StringIO()
    utils_module._write_line("first", captured_stream)
    utils_module._write_line("second", captured_stream)
    assert captured_stream.getvalue() == "first\nsecond\n"


def test_all_gh_pr_create_segments_returns_empty_when_command_absent() -> None:
    """No ``gh pr create`` invocation → empty list."""
    assert utils_module._all_gh_pr_create_segments("git status && echo done") == []


def test_all_gh_pr_create_segments_returns_one_segment_for_single_invocation() -> None:
    """One invocation → one segment from end-of-match to end-of-string."""
    segments_for_single_invocation = utils_module._all_gh_pr_create_segments(
        "gh pr create --title T --body-file B"
    )
    assert len(segments_for_single_invocation) == 1
    assert "--title T" in segments_for_single_invocation[0]


def test_all_gh_pr_create_segments_returns_two_segments_for_chained_invocations() -> None:
    """Two chained invocations → two separate segments split at ``&&``."""
    segments_for_chained_invocations = utils_module._all_gh_pr_create_segments(
        "gh pr create --web && gh pr create --title T"
    )
    assert len(segments_for_chained_invocations) == 2
    assert "--web" in segments_for_chained_invocations[0]
    assert "--web" not in segments_for_chained_invocations[1]
    assert "--title T" in segments_for_chained_invocations[1]


def test_all_gh_pr_create_segments_splits_on_newline_separator() -> None:
    """Newline counts as a command separator between two ``gh pr create`` invocations."""
    segments_for_newline_chained = utils_module._all_gh_pr_create_segments(
        "gh pr create --web\ngh pr create --title T"
    )
    assert len(segments_for_newline_chained) == 2
    assert "--web" in segments_for_newline_chained[0]
    assert "--title T" in segments_for_newline_chained[1]
