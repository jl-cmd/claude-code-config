"""Tests for shared code_rules_gate.py extracted from skills/bugteam/scripts/.

Covers:
- Module loads from _shared/pr-loop/scripts/ location
- resolve_claude_dev_env_root walks up to find code_rules_enforcer.py
- Path-resolution remains correct in both source layout and ~/.claude install layout
- Behavioral parity with the bugteam source: staged paths, added line maps, gate exit codes
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest.mock
from pathlib import Path
from types import ModuleType

import pytest


def _load_gate_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "code_rules_gate.py"
    spec = importlib.util.spec_from_file_location("code_rules_gate", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate_module = _load_gate_module()


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
    run_git_in_repository(repository_root, "init", "--initial-branch=main")
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


def test_resolve_claude_dev_env_root_walks_up_to_find_enforcer(tmp_path: Path) -> None:
    fake_root = tmp_path / "fake_claude"
    enforcer_path = fake_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    enforcer_path.parent.mkdir(parents=True)
    enforcer_path.write_text("# fake enforcer\n", encoding="utf-8")
    deep_script = fake_root / "_shared" / "pr-loop" / "scripts" / "code_rules_gate.py"
    deep_script.parent.mkdir(parents=True)
    deep_script.write_text("# stub\n", encoding="utf-8")

    resolved_root = gate_module.resolve_claude_dev_env_root(deep_script)

    assert resolved_root == fake_root.resolve()


def test_resolve_claude_dev_env_root_supports_legacy_skills_layout(
    tmp_path: Path,
) -> None:
    fake_root = tmp_path / "fake_dev_env"
    enforcer_path = fake_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    enforcer_path.parent.mkdir(parents=True)
    enforcer_path.write_text("# fake enforcer\n", encoding="utf-8")
    legacy_script = fake_root / "skills" / "bugteam" / "scripts" / "code_rules_gate.py"
    legacy_script.parent.mkdir(parents=True)
    legacy_script.write_text("# stub\n", encoding="utf-8")

    resolved_root = gate_module.resolve_claude_dev_env_root(legacy_script)

    assert resolved_root == fake_root.resolve()


def test_resolve_claude_dev_env_root_raises_when_enforcer_missing(
    tmp_path: Path,
) -> None:
    deep_script = tmp_path / "_shared" / "pr-loop" / "scripts" / "code_rules_gate.py"
    deep_script.parent.mkdir(parents=True)
    deep_script.write_text("# stub\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        gate_module.resolve_claude_dev_env_root(deep_script)


def test_resolve_claude_dev_env_root_from_module_path_finds_real_enforcer() -> None:
    module_path = Path(gate_module.__file__).resolve()
    resolved_root = gate_module.resolve_claude_dev_env_root(module_path)
    expected_enforcer = resolved_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    assert expected_enforcer.is_file()


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
    write_file(temporary_git_repository / "module.py", "first_value = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    staged_content_with_banned_identifier = (
        "first_value = 1\n"
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
    write_file(temporary_git_repository / "module.py", "first_value = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    write_file(
        temporary_git_repository / "module.py", "first_value = 1\nsecond_value = 2\n"
    )
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 0


def test_main_staged_mode_exits_zero_when_nothing_staged(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(temporary_git_repository / "module.py", "first_value = 1\n")
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


def test_added_lines_for_staged_file_returns_parsed_result_when_diff_is_non_empty_even_if_parse_returns_empty(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(
        temporary_git_repository / "sample.py",
        "alpha = 1\nbeta = 2\n",
    )
    commit_all_files(temporary_git_repository, "baseline")
    write_file(
        temporary_git_repository / "sample.py", "alpha = 1\nbeta = 2\ngamma = 3\n"
    )
    stage_file(temporary_git_repository, "sample.py")

    monkeypatch.setattr(gate_module, "parse_added_line_numbers", lambda _text: set())

    added_line_numbers = gate_module.added_lines_for_staged_file(
        temporary_git_repository,
        "sample.py",
    )

    assert added_line_numbers == set()


def test_staged_file_line_count_escalates_on_git_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failing_completed = unittest.mock.MagicMock()
    failing_completed.returncode = 128
    failing_completed.stdout = ""
    failing_completed.stderr = "fatal: bad object HEAD"

    with unittest.mock.patch("subprocess.run", return_value=failing_completed):
        with pytest.raises(SystemExit) as exit_info:
            gate_module.staged_file_line_count(tmp_path, "missing.py")

    assert exit_info.value.code == 2
    captured = capsys.readouterr()
    assert "fatal: bad object HEAD" in captured.err


def test_is_staged_file_newly_added_escalates_on_git_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failing_completed = unittest.mock.MagicMock()
    failing_completed.returncode = 128
    failing_completed.stdout = ""
    failing_completed.stderr = "fatal: not a git repository"

    with unittest.mock.patch("subprocess.run", return_value=failing_completed):
        with pytest.raises(SystemExit) as exit_info:
            gate_module.is_staged_file_newly_added(tmp_path, "missing.py")

    assert exit_info.value.code == 2
    captured = capsys.readouterr()
    assert "fatal: not a git repository" in captured.err


def test_check_wrapper_plumb_through_flags_direct_same_file_call() -> None:
    source = (
        "def fetch(target, *, retries=3):\n"
        "    return target\n"
        "\n"
        "def public_fetch(target):\n"
        "    return fetch(target)\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert any(
        "public_fetch" in each_issue and "retries" in each_issue
        for each_issue in issues
    ), (
        "Direct same-file call (ast.Name) must be detected as a wrapper that "
        "drops optional kwargs of its delegate"
    )


def test_check_wrapper_plumb_through_still_flags_attribute_call() -> None:
    source = (
        "def fetch(target, *, retries=3):\n"
        "    return target\n"
        "\n"
        "def public_fetch(target):\n"
        "    return self.fetch(target)\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert any(
        "public_fetch" in each_issue and "retries" in each_issue
        for each_issue in issues
    )


def test_split_violations_by_scope_accepts_all_added_line_numbers_param_name() -> None:
    blocking_issues, advisory_issues = gate_module.split_violations_by_scope(
        ["Line 5: violation"],
        all_added_line_numbers={5},
    )
    assert blocking_issues == ["Line 5: violation"]
    assert advisory_issues == []


def test_run_gate_accepts_added_lines_by_path_param_name(tmp_path: Path) -> None:
    gate_module.run_gate(
        validate_content=lambda _content, _path, **_kwargs: [],
        all_file_paths=[],
        repository_root=tmp_path,
        added_lines_by_path=None,
    )


def test_whole_file_line_set_handles_non_cp1252_utf8(tmp_path: Path) -> None:
    utf8_only_path = tmp_path / "utf8_only.py"
    cp1252_invalid_codepoint = chr(0x81)
    utf8_only_path.write_bytes(
        f"control = '{cp1252_invalid_codepoint}'\nname = 'café'\n".encode("utf-8")
    )

    line_numbers = gate_module.whole_file_line_set(utf8_only_path)

    assert line_numbers == {1, 2}
