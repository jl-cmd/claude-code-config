from __future__ import annotations

import subprocess
import sys
import unittest.mock
from pathlib import Path
import pytest

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import bugteam_code_rules_gate as gate_module


def run_git_in_repository(repository_root: Path, *arguments: str) -> str:
    completion = subprocess.run(
        ["git", *arguments],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return completion.stdout


def initialize_git_repository(repository_root: Path) -> None:
    run_git_in_repository(repository_root, "init")
    run_git_in_repository(repository_root, "symbolic-ref", "HEAD", "refs/heads/main")
    run_git_in_repository(repository_root, "config", "user.email", "test@example.com")
    run_git_in_repository(repository_root, "config", "user.name", "Test")
    run_git_in_repository(repository_root, "config", "commit.gpgsign", "false")


def commit_all_files(repository_root: Path, commit_message: str) -> None:
    run_git_in_repository(repository_root, "add", "-A")
    run_git_in_repository(repository_root, "commit", "-m", commit_message)


def write_file(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def stage_file(repository_root: Path, relative_path: str) -> None:
    run_git_in_repository(repository_root, "add", "--", relative_path)


@pytest.fixture()
def temporary_git_repository(tmp_path: Path) -> Path:
    repository_root = tmp_path / "repository_under_test"
    repository_root.mkdir()
    initialize_git_repository(repository_root)
    return repository_root


def test_paths_from_git_staged_returns_staged_files(
    temporary_git_repository: Path,
) -> None:
    write_file(temporary_git_repository / "committed_file.py", "one = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    write_file(temporary_git_repository / "newly_staged_file.py", "two = 2\n")
    write_file(temporary_git_repository / "unstaged_file.py", "three = 3\n")
    stage_file(temporary_git_repository, "newly_staged_file.py")

    staged_paths = gate_module.paths_from_git_staged(temporary_git_repository)

    staged_names = {path.name for path in staged_paths}
    assert "newly_staged_file.py" in staged_names
    assert "unstaged_file.py" not in staged_names
    assert "committed_file.py" not in staged_names


def test_added_lines_for_staged_file_reports_new_lines(
    temporary_git_repository: Path,
) -> None:
    write_file(temporary_git_repository / "target.py", "first = 1\nsecond = 2\n")
    commit_all_files(temporary_git_repository, "baseline")
    write_file(
        temporary_git_repository / "target.py",
        "first = 1\nsecond = 2\nthird = 3\nfourth = 4\n",
    )
    stage_file(temporary_git_repository, "target.py")

    added_line_numbers = gate_module.added_lines_for_staged_file(
        temporary_git_repository,
        "target.py",
    )

    assert 3 in added_line_numbers
    assert 4 in added_line_numbers
    assert 1 not in added_line_numbers
    assert 2 not in added_line_numbers


def test_added_lines_for_staged_file_treats_new_file_as_fully_added(
    temporary_git_repository: Path,
) -> None:
    write_file(temporary_git_repository / "existing.py", "ignored = 0\n")
    commit_all_files(temporary_git_repository, "baseline")
    write_file(
        temporary_git_repository / "brand_new.py",
        "alpha = 1\nbeta = 2\ngamma = 3\n",
    )
    stage_file(temporary_git_repository, "brand_new.py")

    added_line_numbers = gate_module.added_lines_for_staged_file(
        temporary_git_repository,
        "brand_new.py",
    )

    assert added_line_numbers == {1, 2, 3}


def test_paths_from_git_staged_uses_null_delimiter(
    temporary_git_repository: Path,
) -> None:
    write_file(temporary_git_repository / "first.py", "a = 1\n")
    write_file(temporary_git_repository / "second.py", "b = 2\n")
    commit_all_files(temporary_git_repository, "baseline")
    write_file(temporary_git_repository / "first.py", "a = 10\n")
    write_file(temporary_git_repository / "second.py", "b = 20\n")
    stage_file(temporary_git_repository, "first.py")
    stage_file(temporary_git_repository, "second.py")

    staged_paths = gate_module.paths_from_git_staged(temporary_git_repository)

    staged_names = {path.name for path in staged_paths}
    assert staged_names == {"first.py", "second.py"}


def test_paths_from_git_staged_warns_and_skips_non_utf8_filename(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    non_utf8_raw = b"valid.py\x00\xff\xfe_bad.py\x00"
    mock_completed = unittest.mock.MagicMock()
    mock_completed.returncode = 0
    mock_completed.stdout = non_utf8_raw

    with unittest.mock.patch("subprocess.run", return_value=mock_completed):
        result_paths = gate_module.paths_from_git_staged(tmp_path)

    captured = capsys.readouterr()
    assert "non-UTF-8" in captured.err
    assert len(result_paths) == 1
    assert result_paths[0].name == "valid.py"


def test_staged_added_lines_by_file_maps_every_staged_code_file(
    temporary_git_repository: Path,
) -> None:
    write_file(temporary_git_repository / "already_committed.py", "zero = 0\n")
    commit_all_files(temporary_git_repository, "initial")
    write_file(
        temporary_git_repository / "already_committed.py",
        "zero = 0\nappended = 1\n",
    )
    write_file(temporary_git_repository / "added_file.py", "only = 1\n")
    stage_file(temporary_git_repository, "already_committed.py")
    stage_file(temporary_git_repository, "added_file.py")

    staged_paths = gate_module.paths_from_git_staged(temporary_git_repository)
    added_lines_map = gate_module.added_lines_by_file_staged(
        temporary_git_repository,
        staged_paths,
    )

    resolved_repository_root = temporary_git_repository.resolve()
    assert added_lines_map[resolved_repository_root / "already_committed.py"] == {2}
    assert added_lines_map[resolved_repository_root / "added_file.py"] == {1}


def test_main_staged_mode_blocks_when_staged_lines_introduce_violations(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(temporary_git_repository / "module.py", "first_count = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    staged_content_with_banned_identifier = (
        "first_count = 1\n"
        "def compute_total(operand):\n"
        "    result = operand + 1\n"
        "    return result\n"
    )
    write_file(
        temporary_git_repository / "module.py",
        staged_content_with_banned_identifier,
    )
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1


def test_main_staged_mode_passes_when_no_staged_violations(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(temporary_git_repository / "module.py", "first_count = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    write_file(
        temporary_git_repository / "module.py", "first_count = 1\nsecond_count = 2\n"
    )
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 0


def test_main_staged_mode_exits_zero_when_nothing_staged(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(temporary_git_repository / "module.py", "first_count = 1\n")
    commit_all_files(temporary_git_repository, "initial")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 0


def test_added_lines_for_staged_file_returns_empty_for_modified_file_with_no_additions(
    temporary_git_repository: Path,
) -> None:
    write_file(
        temporary_git_repository / "existing.py",
        "alpha = 1\nbeta = 2\ngamma = 3\n",
    )
    commit_all_files(temporary_git_repository, "baseline")
    write_file(temporary_git_repository / "existing.py", "alpha = 1\nbeta = 2\n")
    stage_file(temporary_git_repository, "existing.py")

    added_line_numbers = gate_module.added_lines_for_staged_file(
        temporary_git_repository,
        "existing.py",
    )

    assert added_line_numbers == set()


def test_is_file_absent_in_index_head_does_not_exist_in_module() -> None:
    assert not hasattr(gate_module, "is_file_absent_in_index_head")


def test_staged_file_line_count_raises_on_git_show_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """git show failure must surface as SystemExit + stderr, never silent 0."""
    failing_completed = unittest.mock.MagicMock()
    failing_completed.returncode = 128
    failing_completed.stdout = ""
    failing_completed.stderr = "fatal: bad object :missing\n"
    with unittest.mock.patch("subprocess.run", return_value=failing_completed):
        with pytest.raises(SystemExit):
            gate_module.staged_file_line_count(tmp_path, "missing.py")
    captured = capsys.readouterr()
    assert "git show" in captured.err
    assert "fatal: bad object" in captured.err


def test_is_staged_file_newly_added_raises_on_git_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """git diff --name-status failure must surface as SystemExit + stderr."""
    failing_completed = unittest.mock.MagicMock()
    failing_completed.returncode = 128
    failing_completed.stdout = ""
    failing_completed.stderr = "fatal: not a git repository\n"
    with unittest.mock.patch("subprocess.run", return_value=failing_completed):
        with pytest.raises(SystemExit):
            gate_module.is_staged_file_newly_added(tmp_path, "anything.py")
    captured = capsys.readouterr()
    assert "git diff --cached --name-status" in captured.err


def test_whole_file_line_set_raises_system_exit_on_oserror(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """OSError reading a file must propagate as SystemExit, not silently return ``set()``.

    Regression for loop1-7: returning an empty set on OSError caused the gate
    to route every violation to the advisory bucket and exit 0 — silently
    downgrading blocking violations to non-blocking on a read failure.
    """
    unreadable_path = tmp_path / "broken.py"
    with unittest.mock.patch.object(
        Path, "read_text", side_effect=PermissionError("denied")
    ):
        with pytest.raises(SystemExit):
            gate_module.whole_file_line_set(unreadable_path)
    captured = capsys.readouterr()
    assert str(unreadable_path) in captured.err
    assert "denied" in captured.err or "PermissionError" in captured.err


def test_check_database_column_string_magic_signals_cap_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the issue cap is hit, a 'cap reached' note must reach stderr."""
    source_with_many_column_tuples = "\n".join(
        [
            "def write_rows():",
            "    rows = [",
            *[
                f"        ('column_name_{each_index}', {each_index}),"
                for each_index in range(10)
            ],
            "    ]",
            "    return rows",
        ]
    )
    issues = gate_module.check_database_column_string_magic(
        source_with_many_column_tuples,
        "production/file.py",
    )
    assert len(issues) == 3
    captured = capsys.readouterr()
    assert "cap reached" in captured.err.lower()


def test_check_wrapper_plumb_through_signals_cap_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """check_wrapper_plumb_through must signal when MAXIMUM_ISSUES_TO_REPORT trims."""
    delegate_definition = (
        "def delegate(*, optional_one=1, optional_two=2, optional_three=3,"
        " optional_four=4): return 0\n"
    )
    wrappers_block = "\n".join(
        f"def wrapper_{each_index}():\n    return self.delegate()"
        for each_index in range(5)
    )
    source_with_many_wrappers = delegate_definition + wrappers_block + "\n"
    issues = gate_module.check_wrapper_plumb_through(
        source_with_many_wrappers,
        "production/wrappers.py",
    )
    assert len(issues) == 3
    captured = capsys.readouterr()
    assert "cap reached" in captured.err.lower()


def test_run_gate_exits_nonzero_when_a_file_is_unreadable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Skipping an unreadable file during run_gate must cause a non-zero exit."""
    target_file = tmp_path / "sample.py"
    target_file.write_text("clean = 1\n", encoding="utf-8")

    def fake_validate(_content: str, _path: str, **_kwargs: object) -> list[str]:
        return []

    with unittest.mock.patch.object(
        Path, "read_text", side_effect=PermissionError("denied")
    ):
        exit_code = gate_module.run_gate(
            fake_validate,
            [target_file],
            tmp_path,
            all_added_lines_map=None,
        )
    captured = capsys.readouterr()
    assert exit_code != 0, (
        "Files skipped due to read errors must produce a non-zero gate exit"
    )
    assert "skip unreadable" in captured.err


def test_added_lines_for_staged_file_returns_parsed_result_when_diff_is_non_empty_even_if_parse_returns_empty(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(
        temporary_git_repository / "sample.py",
        "alpha = 1\nbeta = 2\n",
    )
    commit_all_files(temporary_git_repository, "baseline")
    write_file(temporary_git_repository / "sample.py", "alpha = 1\nbeta = 2\ngamma = 3\n")
    stage_file(temporary_git_repository, "sample.py")

    monkeypatch.setattr(gate_module, "parse_added_line_numbers", lambda _text: set())

    added_line_numbers = gate_module.added_lines_for_staged_file(
        temporary_git_repository,
        "sample.py",
    )

    assert added_line_numbers == set()


def _build_function_module(
    function_name: str, body_line_count: int, leading_lines: int
) -> str:
    preamble = "".join("anchor_name\n" for _ in range(leading_lines))
    body = "\n".join("    keep_alive_name" for _ in range(body_line_count))
    return f"{preamble}def {function_name}() -> None:\n{body}\n"


def test_split_violations_blocks_function_length_when_span_intersects_added_lines() -> None:
    """A function-length issue whose declared span overlaps the diff's added
    lines is blocking — the body grew, which is the regression intent."""
    validate_content = gate_module.load_validate_content()
    long_function = _build_function_module(
        "oversized", body_line_count=70, leading_lines=3
    )
    issues = validate_content(long_function, "src/long_module.py", "")
    function_length_issues = [
        each_issue for each_issue in issues if "blocking threshold" in each_issue
    ]
    assert function_length_issues, f"expected a function-length issue, got {issues!r}"
    span_def_line = 4
    inside_span_line = span_def_line + 10
    blocking, advisory = gate_module.split_violations_by_scope(
        function_length_issues,
        all_added_line_numbers={inside_span_line},
    )
    assert blocking == function_length_issues
    assert advisory == []


def test_split_violations_advises_function_length_when_span_misses_added_lines() -> None:
    """A function-length issue for an untouched pre-existing function — whose
    declared span does not overlap any added line — is advisory, not blocking.
    Prevents the over-block regression where every pre-existing long function
    in a touched file was forced into the blocking payload."""
    validate_content = gate_module.load_validate_content()
    long_function = _build_function_module(
        "oversized", body_line_count=70, leading_lines=3
    )
    issues = validate_content(long_function, "src/long_module.py", "")
    function_length_issues = [
        each_issue for each_issue in issues if "blocking threshold" in each_issue
    ]
    assert function_length_issues, f"expected a function-length issue, got {issues!r}"
    line_far_outside_span = 5000
    blocking, advisory = gate_module.split_violations_by_scope(
        function_length_issues,
        all_added_line_numbers={line_far_outside_span},
    )
    assert advisory == function_length_issues
    assert blocking == []


def _isolation_issues_for_home_probe_test() -> list[str]:
    validate_content = gate_module.load_validate_content()
    header = "from pathlib import Path\n"
    test_body = (
        "def test_reads_home() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    issues = validate_content(header + test_body, "src/test_module.py", "")
    return [each_issue for each_issue in issues if "probes" in each_issue]


def test_split_violations_blocks_isolation_when_function_span_intersects_added_lines() -> None:
    """An isolation issue whose enclosing test-function span overlaps the diff's
    added lines is blocking — a signature-line change that un-isolates an
    unchanged-body probe must block, matching the enforcer's terminal path."""
    isolation_issues = _isolation_issues_for_home_probe_test()
    assert isolation_issues, "expected an isolation issue from the HOME probe test"
    signature_line = 2
    blocking, advisory = gate_module.split_violations_by_scope(
        isolation_issues,
        all_added_line_numbers={signature_line},
    )
    assert blocking == isolation_issues
    assert advisory == []


def test_split_violations_advises_isolation_when_function_span_misses_added_lines() -> None:
    """An isolation issue for an untouched pre-existing probe — whose enclosing
    test-function span does not overlap any added line — is advisory, not
    blocking, mirroring the function-length scope contract."""
    isolation_issues = _isolation_issues_for_home_probe_test()
    assert isolation_issues, "expected an isolation issue from the HOME probe test"
    line_far_outside_span = 5000
    blocking, advisory = gate_module.split_violations_by_scope(
        isolation_issues,
        all_added_line_numbers={line_far_outside_span},
    )
    assert advisory == isolation_issues
    assert blocking == []


def _oversized_function_text(function_name: str) -> str:
    body = "\n".join("    keep_alive_name" for _ in range(70))
    return f"def {function_name}() -> None:\n{body}\n"


def _short_function_text(function_name: str) -> str:
    return f"def {function_name}() -> None:\n    keep_alive_name\n"


def test_main_blocks_sixth_long_function_on_added_lines_past_document_order(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bugbot-2: with five pre-existing untouched long functions ahead of it in
    document order, growing the sixth function past the threshold on staged
    lines must still block at the bugteam gate. The gate scopes by added lines,
    so the in-scope sixth violation blocks regardless of how many untouched
    ones precede it."""
    leading_long_functions = "".join(
        _oversized_function_text(f"leading_long_{each_index}")
        for each_index in range(5)
    )
    baseline = leading_long_functions + _short_function_text("target_function")
    write_file(temporary_git_repository / "module.py", baseline)
    commit_all_files(temporary_git_repository, "five long functions plus a short sixth")

    grown = leading_long_functions + _oversized_function_text("target_function")
    write_file(temporary_git_repository / "module.py", grown)
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1, (
        "the sixth long function — the only one on staged lines — must block "
        "even though five untouched long functions precede it in document order"
    )


def _home_probe_test_text(test_name: str) -> str:
    return (
        f"def {test_name}() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )


def _clean_test_text(test_name: str) -> str:
    return f"def {test_name}() -> None:\n    assert 1 + 1 == 2\n"


def test_main_blocks_sixth_isolation_probe_on_added_lines_past_document_order(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bugbot-2 mirror: with five pre-existing untouched HOME probes ahead of it
    in document order, adding a HOME probe to the sixth test on staged lines
    must still block at the bugteam gate. The gate scopes by added lines, so the
    in-scope sixth probe blocks regardless of how many untouched ones precede
    it."""
    header = "from pathlib import Path\n"
    leading_probe_tests = "".join(
        _home_probe_test_text(f"test_leading_probe_{each_index}")
        for each_index in range(5)
    )
    baseline = header + leading_probe_tests + _clean_test_text("test_target_probe")
    write_file(temporary_git_repository / "test_module.py", baseline)
    commit_all_files(temporary_git_repository, "five probe tests plus a clean sixth")

    grown = header + leading_probe_tests + _home_probe_test_text("test_target_probe")
    write_file(temporary_git_repository / "test_module.py", grown)
    stage_file(temporary_git_repository, "test_module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1, (
        "the sixth HOME probe — the only one on staged lines — must block even "
        "though five untouched probes precede it in document order"
    )


def _banned_noun_function_text(index: int) -> str:
    return (
        f"def leading_{index}(canned_results: int) -> int:\n"
        f"    return canned_results\n"
    )


def test_main_blocks_banned_noun_on_added_lines_past_document_order(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """loop7-P1: with three pre-existing untouched banned-noun identifiers ahead
    of it in document order, introducing a fourth banned-noun on a staged line
    must still block at the bugteam gate. The gate scopes by added lines, so the
    in-scope identifier blocks regardless of how many untouched ones precede
    it."""
    leading_count = 3
    leading_functions = "".join(
        _banned_noun_function_text(each_index) for each_index in range(leading_count)
    )
    baseline = leading_functions + "def placeholder() -> int:\n    return 0\n"
    write_file(temporary_git_repository / "module.py", baseline)
    commit_all_files(temporary_git_repository, "three banned nouns plus a clean function")

    grown = leading_functions + "def aggregate(holiday_result: int) -> int:\n    return holiday_result\n"
    write_file(temporary_git_repository / "module.py", grown)
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1, (
        "the fourth banned-noun identifier — the only one on staged lines — must "
        "block even though three untouched ones precede it in document order"
    )


def test_report_partitioned_violations_returns_zero_when_clean(tmp_path: Path) -> None:
    """No blocking violations and no skipped files yields a zero exit code."""
    exit_code = gate_module._report_partitioned_violations(
        blocking_by_file={},
        advisory_by_file={tmp_path / "a.py": ["Line 1: advisory only"]},
        repository_root=tmp_path,
        is_whole_file_scope=False,
        skipped_unreadable_count=0,
    )
    assert exit_code == 0


def test_report_partitioned_violations_returns_one_on_blocking(tmp_path: Path) -> None:
    """A blocking violation yields a non-zero exit code."""
    exit_code = gate_module._report_partitioned_violations(
        blocking_by_file={tmp_path / "a.py": ["Line 1: blocking violation"]},
        advisory_by_file={},
        repository_root=tmp_path,
        is_whole_file_scope=False,
        skipped_unreadable_count=0,
    )
    assert exit_code == 1


def test_report_partitioned_violations_returns_one_when_file_skipped(tmp_path: Path) -> None:
    """A skipped unreadable file forces a non-zero exit even with no blocking
    violations, because the gate cannot vouch for the file it could not read."""
    exit_code = gate_module._report_partitioned_violations(
        blocking_by_file={},
        advisory_by_file={},
        repository_root=tmp_path,
        is_whole_file_scope=False,
        skipped_unreadable_count=1,
    )
    assert exit_code == 1
