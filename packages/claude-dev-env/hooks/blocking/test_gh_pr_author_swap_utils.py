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


def test_strip_quoted_regions_preserves_backtick_substitution_inside_double_quotes() -> None:
    """`gh pr create` inside a backtick substitution inside double quotes stays scannable."""
    original_command = 'echo "`gh pr create --title T`"'
    stripped_command = utils_module._strip_quoted_regions(original_command)
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
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("gh pr create --title T")
    )


def test_command_invokes_gh_pr_create_matches_chained_form() -> None:
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("git push && gh pr create")
    )


def test_command_invokes_gh_pr_create_rejects_pr_edit() -> None:
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("gh pr edit 10 --title X")
    )


def test_command_invokes_gh_pr_create_rejects_substring() -> None:
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("some-gh pr created-by")
    )


def test_command_invokes_gh_pr_create_ignores_literal_inside_double_quotes() -> None:
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions('echo "gh pr create docs"')
    )


def test_command_invokes_gh_pr_create_ignores_literal_inside_single_quotes() -> None:
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("echo 'gh pr create docs'")
    )


def test_command_invokes_gh_pr_create_detects_backtick_substitution_body() -> None:
    """Backtick substitution body executes, so an inner ``gh pr create`` is real."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("echo `gh pr create docs`")
    )


def test_command_invokes_gh_pr_create_detects_dollar_paren_substitution_body() -> None:
    """``$(...)`` substitution body executes, so an inner ``gh pr create`` is real."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions('echo "$(gh pr create docs)"')
    )


def test_command_invokes_gh_pr_create_still_matches_unquoted_invocation() -> None:
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions(
            'gh pr create --body "see docs about gh pr create"'
        )
    )


def test_strip_quoted_regions_balances_paren_inside_double_quoted_substitution_body() -> None:
    """A ``)`` inside ``"..."`` within ``$(...)`` must not prematurely close the substitution."""
    original_command = 'echo $(echo ")") && gh pr create --title T'
    stripped_command = utils_module._strip_quoted_regions(original_command)
    assert len(stripped_command) == len(original_command)
    assert "gh pr create" in stripped_command


def test_command_invokes_gh_pr_create_detects_real_invocation_after_double_quoted_paren_in_substitution() -> None:
    """The real ``gh pr create`` after a ``$(echo ")")`` block must still be detected."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions('echo $(echo ")") && gh pr create --title T')
    )


def test_strip_quoted_regions_balances_paren_inside_single_quoted_substitution_body() -> None:
    """A ``)`` inside ``'...'`` within ``$(...)`` must not prematurely close the substitution."""
    original_command = "echo $(echo ')') && gh pr create --title T"
    stripped_command = utils_module._strip_quoted_regions(original_command)
    assert len(stripped_command) == len(original_command)
    assert "gh pr create" in stripped_command


def test_command_invokes_gh_pr_create_detects_real_invocation_after_single_quoted_paren_in_substitution() -> None:
    """The real ``gh pr create`` after a ``$(echo ')')`` block must still be detected."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("echo $(echo ')') && gh pr create --title T")
    )


def test_command_invokes_gh_pr_create_detects_real_invocation_after_escaped_quote_in_substitution() -> None:
    """A ``\\"`` inside ``"..."`` in ``$(...)`` does not close the quoted region; balance still holds."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions('echo $(echo "\\")") && gh pr create --title T')
    )


def test_command_invokes_gh_pr_create_detects_real_invocation_after_backtick_paren_in_substitution() -> None:
    """A ``)`` inside ``` `...` ``` within ``$(...)`` must not prematurely close the substitution."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("echo $(echo `foo)bar`) && gh pr create --title T")
    )


def test_command_invokes_gh_pr_create_detects_real_invocation_after_subshell_in_substitution() -> None:
    """A bash subshell ``(echo b)`` inside ``$(...)`` must not prematurely close the outer substitution."""
    command = '''echo "$(printf 'before'; (echo nested); printf 'after')" && gh pr create --title T'''
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions(command)
    )


def test_command_invokes_gh_pr_create_detects_real_invocation_after_array_in_substitution() -> None:
    """A bash array assignment ``arr=(a b c)`` inside ``$(...)`` must not prematurely close the outer substitution."""
    command = '''echo "$(arr=(a b c); echo "${arr[@]}")" && gh pr create --title T'''
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions(command)
    )


def test_command_invokes_gh_pr_create_detects_real_invocation_after_function_in_substitution() -> None:
    """A bash function definition ``f() { ... }`` inside ``$(...)`` must not prematurely close the outer substitution."""
    command = '''echo "$(f() { echo z; }; f)" && gh pr create --title T'''
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions(command)
    )


def test_command_invokes_gh_pr_create_detects_invocation_after_nested_substitution_in_double_quoted_region() -> None:
    """A ``$(...)`` nested inside a ``"..."`` inside an outer ``$(...)`` must not flip the outer quoted boundary."""
    command = '''echo "$(echo "$(echo "deeply nested")")" && gh pr create --title T'''
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions(command)
    )


def test_command_invokes_gh_pr_create_detects_invocation_after_backtick_substitution_in_double_quoted_region() -> None:
    """A ``` `...` ``` nested inside a ``"..."`` inside an outer ``$(...)`` must not flip the outer quoted boundary."""
    command = '''echo "$(echo "`echo nested`")" && gh pr create --title T'''
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions(command)
    )


def test_command_invokes_gh_pr_create_rejects_newline_between_pr_and_create() -> None:
    """``gh pr\\ncreate-report.sh`` is two commands; the second is not ``create``."""
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("gh pr\ncreate-report.sh")
    )


def test_command_invokes_gh_pr_create_matches_tab_separated_tokens() -> None:
    """Tab characters between ``gh``, ``pr``, and ``create`` still match the invocation pattern."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("gh\tpr\tcreate --title T")
    )


def test_command_invokes_gh_pr_create_matches_short_repo_flag() -> None:
    """``gh -R owner/repo pr create`` must match — the short repo flag separates ``gh`` from ``pr``."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("gh -R foo/bar pr create --title T")
    )


def test_command_invokes_gh_pr_create_matches_long_repo_flag_with_space() -> None:
    """``gh --repo owner/repo pr create`` must match — space-separated long flag plus value."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("gh --repo foo/bar pr create --title T")
    )


def test_command_invokes_gh_pr_create_matches_long_repo_flag_with_equals() -> None:
    """``gh --repo=owner/repo pr create`` must match — equals-attached long flag value."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("gh --repo=foo/bar pr create --title T")
    )


def test_command_invokes_gh_pr_create_matches_multiple_intervening_flags() -> None:
    """Multiple top-level flags between ``gh`` and ``pr create`` must all be tolerated."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("gh -R foo/bar --hostname github.com pr create")
    )


def test_command_invokes_gh_pr_create_rejects_gh_dash_pr_create() -> None:
    """``gh-pr-create`` is a single hyphenated token, not an invocation of ``gh pr create``."""
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("gh-pr-create --foo")
    )


def test_command_invokes_gh_pr_create_still_matches_basic_form() -> None:
    """Regression — the original ``gh pr create`` form must continue to match after pattern widening."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("gh pr create --title T")
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


def test_strip_quoted_regions_blanks_single_quoted_argument_inside_substitution() -> None:
    """Regression for finding 2: ``$(printf 'gh pr create')`` must not leak the literal command.

    The substitution executes ``printf`` against the literal data
    ``gh pr create`` — the data must not be confused with a real
    ``gh pr create`` invocation. Quoted regions inside substitution
    bodies are blanked the same way as top-level quoted regions, so
    the matcher sees ``$(printf                 )`` after stripping.
    """
    original_command = "echo $(printf 'gh pr create')"
    stripped_command = utils_module._strip_quoted_regions(original_command)
    assert len(stripped_command) == len(original_command)
    assert "gh pr create" not in stripped_command


def test_command_invokes_gh_pr_create_rejects_data_argument_inside_substitution() -> None:
    """Regression for finding 2: ``echo $(printf 'gh pr create')`` runs printf, not gh pr create."""
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("echo $(printf 'gh pr create')")
    )


def test_command_invokes_gh_pr_create_rejects_double_quoted_substitution_data() -> None:
    """Regression for finding 2: ``$(printf "gh pr create")`` runs printf, not gh pr create."""
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions('echo $(printf "gh pr create")')
    )


def test_command_invokes_gh_pr_create_still_detects_real_invocation_inside_substitution() -> None:
    """Regression for finding 2 guard: ``$(gh pr create)`` runs the real command — must still match."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("echo $(gh pr create --title T)")
    )


def test_command_invokes_gh_pr_create_rejects_echo_argument() -> None:
    """Regression for finding 3: ``echo gh pr create`` is data passed to echo, not a command."""
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_quoted_regions("echo gh pr create")
    )


def test_command_invokes_gh_pr_create_rejects_inline_bash_comment() -> None:
    """Regression for finding 3: ``git status # gh pr create later`` is a comment, not a command."""
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_bash_comments(
            utils_module._strip_quoted_regions("git status # gh pr create later")
        )
    )


def test_command_invokes_gh_pr_create_rejects_standalone_bash_comment() -> None:
    """A line that begins with ``#`` is entirely comment — no command, no match."""
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_bash_comments(
            utils_module._strip_quoted_regions("# gh pr create later")
        )
    )


def test_command_invokes_gh_pr_create_still_matches_after_comment_on_prior_line() -> None:
    """A comment on a prior line is stripped; the real ``gh pr create`` on the next line still matches."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._strip_bash_comments(
            utils_module._strip_quoted_regions("# leave it commented\ngh pr create --title T")
        )
    )


def test_preprocess_command_for_matching_chains_strip_and_comments() -> None:
    """The combined preprocess pipeline blanks quotes then comments in one step."""
    preprocessed_command = utils_module._preprocess_command_for_matching(
        'git status # gh pr create later --body "see docs"'
    )
    assert "see docs" not in preprocessed_command
    assert "gh pr create" not in preprocessed_command


def test_strip_substitution_bodies_replaces_dollar_paren_body_with_spaces() -> None:
    """Regression for finding 4: ``$(echo --web)`` body is blanked so ``--web`` no longer leaks."""
    quote_stripped_command = utils_module._strip_quoted_regions(
        'gh pr create --title "$(echo --web)" --body-file B'
    )
    bodies_blanked_command = utils_module._strip_substitution_bodies(quote_stripped_command)
    assert len(bodies_blanked_command) == len(quote_stripped_command)
    assert "--web" not in bodies_blanked_command


def test_strip_substitution_bodies_replaces_backtick_body_with_spaces() -> None:
    """Regression for finding 4: backtick body is blanked so ``--web`` inside does not leak."""
    quote_stripped_command = utils_module._strip_quoted_regions(
        "gh pr create --title `echo --web` --body-file B"
    )
    bodies_blanked_command = utils_module._strip_substitution_bodies(quote_stripped_command)
    assert len(bodies_blanked_command) == len(quote_stripped_command)
    assert "--web" not in bodies_blanked_command


def test_switch_gh_account_returns_false_on_permission_error() -> None:
    """Regression for finding 5: ``PermissionError`` from subprocess.run must be caught as failure."""
    with mock.patch.object(utils_module.subprocess, "run", side_effect=PermissionError):
        assert utils_module._switch_gh_account("JonEcho") is False


def test_switch_gh_account_returns_false_on_generic_os_error() -> None:
    """Any ``OSError`` subclass from subprocess.run must follow the documented failure path."""
    with mock.patch.object(utils_module.subprocess, "run", side_effect=OSError("spawn refused")):
        assert utils_module._switch_gh_account("JonEcho") is False


def test_command_invokes_gh_pr_create_matches_paren_subshell_prefix() -> None:
    """``( gh pr create --title T )`` is a real paren subshell — must match.

    Bash executes commands inside ``( ... )`` in a subshell. The
    boundary class in ``GH_PR_CREATE_PATTERN`` includes ``(`` so the
    enforcer recognises the invocation.
    """
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching("( gh pr create --title T )")
    )


def test_command_invokes_gh_pr_create_matches_brace_group_prefix() -> None:
    """``{ gh pr create --title T ; }`` is a real brace group — must match.

    Bash executes commands inside ``{ ...; }`` in the current shell.
    The boundary class in ``GH_PR_CREATE_PATTERN`` includes ``{`` so
    the enforcer recognises the invocation.
    """
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching("{ gh pr create --title T ; }")
    )


def test_command_invokes_gh_pr_create_matches_single_env_var_prefix() -> None:
    """``GH_DEBUG=1 gh pr create --title T`` is a real invocation with an env var assignment.

    Bash applies the assignment to the ``gh`` process environment. The
    pattern allows zero or more ``VAR=VALUE`` prefix segments before
    the ``gh`` command name.
    """
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching("GH_DEBUG=1 gh pr create --title T")
    )


def test_command_invokes_gh_pr_create_matches_multiple_env_var_prefixes() -> None:
    """Multiple env var assignments stacked before ``gh`` must all be tolerated."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching(
            "GH_DEBUG=1 GH_HOST=github.com gh pr create --title T"
        )
    )


def test_command_invokes_gh_pr_create_rejects_shell_variable_expansion_prefix() -> None:
    """``${var} gh pr create`` is a shell variable expansion, not an env var assignment.

    The env-var-assignment branch of the pattern requires a literal
    ``=`` character in the prefix segment. ``${var}`` carries no ``=``,
    so the pattern correctly rejects it and the matcher returns False.
    """
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching("${var} gh pr create")
    )


def test_strip_bash_comments_strips_comment_inside_dollar_paren_substitution_body() -> None:
    """A ``#`` after whitespace inside ``$(...)`` is a comment INSIDE the substitution.

    The substitution body executes as its own command, so the comment
    must consume the trailing text inside the body — but ONLY up to
    the closing ``)``. The ``echo $(echo ok # ; gh pr create)`` case
    runs ``echo ok`` in the subshell; ``gh pr create`` is comment text
    and must not match.
    """
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching("echo $(echo ok # ; gh pr create)")
    )


def test_strip_bash_comments_strips_comment_inside_backtick_substitution_body() -> None:
    """A ``#`` after whitespace inside ``` `...` ``` is a comment INSIDE the substitution.

    Symmetric with ``$(...)`` — the backtick body executes, so a hash
    after whitespace introduces a comment bounded by the closing
    backtick.
    """
    assert not utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching("echo `echo ok # gh pr create`")
    )


def test_strip_bash_comments_substitution_comment_does_not_consume_closer() -> None:
    """A comment inside a substitution body must terminate at the closer.

    Without the closer-bound, a flat regex sweep would consume the
    ``)`` and every byte after it on the same line, erasing a real
    ``gh pr create`` that follows the substitution. The walker bounds
    the comment at the closer so the trailing command stays visible.
    """
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching(
            "$(date +%H # 24h) && gh pr create --title T"
        )
    )


def test_strip_bash_comments_substitution_comment_in_backtick_does_not_consume_closer() -> None:
    """Backtick variant of the closer-bound: the trailing ``gh pr create`` stays visible."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching(
            "foo `cmd # comment` bar && gh pr create"
        )
    )


def test_strip_bash_comments_real_invocation_inside_substitution_still_matches() -> None:
    """A real ``$(gh pr create)`` (no comment) must still trigger the matcher."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching("echo $(gh pr create)")
    )


def test_strip_bash_comments_real_invocation_after_substitution_still_matches() -> None:
    """``echo $(echo ok); gh pr create`` — the trailing command is OUTSIDE the substitution."""
    assert utils_module._command_invokes_gh_pr_create_in_stripped(
        utils_module._preprocess_command_for_matching("echo $(echo ok); gh pr create")
    )
