"""Failing-first tests for hook_log_extractor.

Covers category derivation (15 known + uncategorized fallback), outcome
mapping (4 attachment types), excerpt truncation, offset advance,
idempotence via ON CONFLICT, offline graceful fallback, and batched
INSERT shape. psycopg is mocked at the connect boundary.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from diagnostic import hook_log_extractor
from config.hook_log_extractor_constants import (
    COMMAND_EXCERPT_MAX_CHARACTERS,
    HOOK_CATEGORY_UNCATEGORIZED,
    KNOWN_HOOK_CATEGORIES,
    OUTCOME_ADDED_CONTEXT,
    OUTCOME_BLOCKED,
    OUTCOME_SUCCESS,
    OUTCOME_SYSTEM_MESSAGE,
    STDERR_EXCERPT_MAX_CHARACTERS,
    STDOUT_EXCERPT_MAX_CHARACTERS,
)


def _make_success_line(
    session_id: str = "session-alpha",
    hook_name: str = "PreToolUse:Bash",
    hook_event: str = "PreToolUse",
    tool_use_id: str = "toolu_001",
    command: str = "python C:/Users/jon/.claude/hooks/blocking/destructive_command_blocker.py",
    stdout: str = "ok\n",
    stderr: str = "",
    exit_code: int = 0,
    duration_ms: int = 42,
    timestamp: str = "2026-04-24T13:32:07.978Z",
    cwd: str = "Y:\\Projects\\repo",
    git_branch: str = "main",
) -> str:
    record = {
        "type": "attachment",
        "attachment": {
            "type": "hook_success",
            "hookName": hook_name,
            "hookEvent": hook_event,
            "toolUseID": tool_use_id,
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "exitCode": exit_code,
            "durationMs": duration_ms,
        },
        "timestamp": timestamp,
        "sessionId": session_id,
        "cwd": cwd,
        "gitBranch": git_branch,
    }
    return json.dumps(record)


def _make_blocking_line(
    session_id: str = "session-alpha",
    hook_name: str = "PreToolUse:Bash",
    hook_event: str = "PreToolUse",
    tool_use_id: str = "toolu_002",
    blocking_message: str = "blocked for reason",
    command: str = "python C:/Users/jon/.claude/hooks/blocking/content_search_to_zoekt_redirector.py",
    timestamp: str = "2026-04-24T13:32:54.293Z",
    cwd: str = "Y:\\Projects\\repo",
    git_branch: str = "main",
) -> str:
    record = {
        "type": "attachment",
        "attachment": {
            "type": "hook_blocking_error",
            "hookName": hook_name,
            "hookEvent": hook_event,
            "toolUseID": tool_use_id,
            "blockingError": {
                "blockingError": blocking_message,
                "command": command,
            },
        },
        "timestamp": timestamp,
        "sessionId": session_id,
        "cwd": cwd,
        "gitBranch": git_branch,
    }
    return json.dumps(record)


def _make_system_message_line(
    session_id: str = "session-alpha",
    hook_name: str = "PreToolUse:Bash",
    hook_event: str = "PreToolUse",
    tool_use_id: str = "toolu_003",
    content: str = "[destructive-gate] blocked",
    timestamp: str = "2026-04-24T13:32:54.293Z",
    cwd: str = "Y:\\Projects\\repo",
    git_branch: str = "main",
) -> str:
    record = {
        "type": "attachment",
        "attachment": {
            "type": "hook_system_message",
            "hookName": hook_name,
            "hookEvent": hook_event,
            "toolUseID": tool_use_id,
            "content": content,
        },
        "timestamp": timestamp,
        "sessionId": session_id,
        "cwd": cwd,
        "gitBranch": git_branch,
    }
    return json.dumps(record)


def _make_additional_context_line(
    session_id: str = "session-alpha",
    hook_name: str = "PreToolUse:Bash",
    hook_event: str = "PreToolUse",
    tool_use_id: str = "toolu_004",
    content: list[str] | None = None,
    timestamp: str = "2026-04-24T13:32:54.293Z",
    cwd: str = "Y:\\Projects\\repo",
    git_branch: str = "main",
) -> str:
    record = {
        "type": "attachment",
        "attachment": {
            "type": "hook_additional_context",
            "hookName": hook_name,
            "hookEvent": hook_event,
            "toolUseID": tool_use_id,
            "content": content or ["extra context"],
        },
        "timestamp": timestamp,
        "sessionId": session_id,
        "cwd": cwd,
        "gitBranch": git_branch,
    }
    return json.dumps(record)


@pytest.mark.parametrize(
    "expected_category",
    sorted(KNOWN_HOOK_CATEGORIES),
)
def test_derive_category_accepts_each_known_category(expected_category: str) -> None:
    script_path = f"python C:/Users/jon/.claude/hooks/{expected_category}/some_hook.py"
    assert hook_log_extractor.derive_category(script_path) == expected_category


def test_derive_category_returns_uncategorized_for_unknown_parent() -> None:
    script_path = "python C:/Users/jon/.claude/hooks/unheard_of_bucket/some_hook.py"
    assert (
        hook_log_extractor.derive_category(script_path) == HOOK_CATEGORY_UNCATEGORIZED
    )


def test_derive_category_returns_uncategorized_for_empty_path() -> None:
    assert hook_log_extractor.derive_category(None) == HOOK_CATEGORY_UNCATEGORIZED
    assert hook_log_extractor.derive_category("") == HOOK_CATEGORY_UNCATEGORIZED


def test_derive_category_handles_windows_backslash_paths() -> None:
    script_path = "python C:\\Users\\jon\\.claude\\hooks\\blocking\\destructive_command_blocker.py"
    assert hook_log_extractor.derive_category(script_path) == "blocking"


def test_derive_category_strips_python_launcher_prefix() -> None:
    script_path = "python3 /home/jon/.claude/hooks/session/code_rules_reminder.py"
    assert hook_log_extractor.derive_category(script_path) == "session"


def test_derive_outcome_maps_hook_success() -> None:
    assert hook_log_extractor.derive_outcome("hook_success") == OUTCOME_SUCCESS


def test_derive_outcome_maps_hook_blocking_error() -> None:
    assert hook_log_extractor.derive_outcome("hook_blocking_error") == OUTCOME_BLOCKED


def test_derive_outcome_maps_hook_system_message() -> None:
    assert (
        hook_log_extractor.derive_outcome("hook_system_message")
        == OUTCOME_SYSTEM_MESSAGE
    )


def test_derive_outcome_maps_hook_additional_context() -> None:
    assert (
        hook_log_extractor.derive_outcome("hook_additional_context")
        == OUTCOME_ADDED_CONTEXT
    )


def test_derive_outcome_raises_on_unknown_type() -> None:
    with pytest.raises(KeyError):
        hook_log_extractor.derive_outcome("hook_something_else")


def test_extract_script_path_from_success_record() -> None:
    record_json = _make_success_line(
        command="python C:/Users/jon/.claude/hooks/blocking/foo.py",
    )
    parsed = json.loads(record_json)
    assert (
        hook_log_extractor.extract_script_path(parsed["attachment"])
        == "C:/Users/jon/.claude/hooks/blocking/foo.py"
    )


def test_extract_script_path_from_blocking_record() -> None:
    record_json = _make_blocking_line(
        command="python3 /home/jon/.claude/hooks/blocking/bar.py",
    )
    parsed = json.loads(record_json)
    assert (
        hook_log_extractor.extract_script_path(parsed["attachment"])
        == "/home/jon/.claude/hooks/blocking/bar.py"
    )


def test_extract_script_path_returns_none_for_system_message() -> None:
    record_json = _make_system_message_line()
    parsed = json.loads(record_json)
    assert hook_log_extractor.extract_script_path(parsed["attachment"]) is None


def test_excerpt_truncation_respects_command_limit() -> None:
    long_command = "x" * (COMMAND_EXCERPT_MAX_CHARACTERS + 50)
    truncated = hook_log_extractor.truncate_command_excerpt(long_command)
    assert len(truncated) == COMMAND_EXCERPT_MAX_CHARACTERS


def test_excerpt_truncation_preserves_short_command() -> None:
    short_command = "python foo.py"
    assert hook_log_extractor.truncate_command_excerpt(short_command) == short_command


def test_excerpt_truncation_handles_none_command() -> None:
    assert hook_log_extractor.truncate_command_excerpt(None) is None


def test_excerpt_truncation_respects_stdout_limit() -> None:
    long_stdout = "y" * (STDOUT_EXCERPT_MAX_CHARACTERS + 100)
    truncated = hook_log_extractor.truncate_stdout_excerpt(long_stdout)
    assert len(truncated) == STDOUT_EXCERPT_MAX_CHARACTERS


def test_excerpt_truncation_respects_stderr_limit() -> None:
    long_stderr = "z" * (STDERR_EXCERPT_MAX_CHARACTERS + 100)
    truncated = hook_log_extractor.truncate_stderr_excerpt(long_stderr)
    assert len(truncated) == STDERR_EXCERPT_MAX_CHARACTERS


def test_build_row_from_success_attachment() -> None:
    record_json = _make_success_line()
    parsed = json.loads(record_json)
    row = hook_log_extractor.build_row_from_attachment(
        parsed_record=parsed,
        source_jsonl_path="C:/fake/path.jsonl",
        source_line_number=1,
    )
    assert row["session_id"] == "session-alpha"
    assert row["hook_event"] == "PreToolUse"
    assert row["hook_name"] == "PreToolUse:Bash"
    assert row["tool_name"] == "Bash"
    assert row["tool_use_id"] == "toolu_001"
    assert row["outcome"] == OUTCOME_SUCCESS
    assert row["exit_code"] == 0
    assert row["duration_ms"] == 42
    assert row["hook_category"] == "blocking"
    assert row["source_jsonl_path"] == "C:/fake/path.jsonl"
    assert row["source_line_number"] == 1


def test_build_row_from_blocking_attachment_has_no_exit_code_or_duration() -> None:
    record_json = _make_blocking_line()
    parsed = json.loads(record_json)
    row = hook_log_extractor.build_row_from_attachment(
        parsed_record=parsed,
        source_jsonl_path="C:/fake/path.jsonl",
        source_line_number=2,
    )
    assert row["outcome"] == OUTCOME_BLOCKED
    assert row["exit_code"] is None
    assert row["duration_ms"] is None
    assert (
        row["stderr_excerpt"] is not None
        and "blocked for reason" in row["stderr_excerpt"]
    )
    assert row["hook_category"] == "blocking"


def test_build_row_from_system_message_uses_content_as_stdout_excerpt() -> None:
    record_json = _make_system_message_line(content="[gate] blocked Bash(grep)")
    parsed = json.loads(record_json)
    row = hook_log_extractor.build_row_from_attachment(
        parsed_record=parsed,
        source_jsonl_path="C:/fake/path.jsonl",
        source_line_number=3,
    )
    assert row["outcome"] == OUTCOME_SYSTEM_MESSAGE
    assert row["stdout_excerpt"] == "[gate] blocked Bash(grep)"


def test_build_row_from_additional_context_joins_list_content() -> None:
    record_json = _make_additional_context_line(content=["first note", "second note"])
    parsed = json.loads(record_json)
    row = hook_log_extractor.build_row_from_attachment(
        parsed_record=parsed,
        source_jsonl_path="C:/fake/path.jsonl",
        source_line_number=4,
    )
    assert row["outcome"] == OUTCOME_ADDED_CONTEXT
    assert row["stdout_excerpt"] is not None
    assert "first note" in row["stdout_excerpt"]
    assert "second note" in row["stdout_excerpt"]


def test_iter_attachment_records_skips_non_attachment_rows(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    lines = [
        json.dumps({"type": "user", "content": "hi"}),
        _make_success_line(),
        json.dumps({"type": "assistant", "content": "hello"}),
        _make_blocking_line(),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    all_parsed_records = list(
        hook_log_extractor.iter_attachment_records_from_file(
            str(jsonl_file), start_offset=0
        ),
    )

    assert len(all_parsed_records) == 2
    first_parsed_record, first_line_number, _first_offset = all_parsed_records[0]
    assert first_parsed_record["attachment"]["type"] == "hook_success"
    assert first_line_number == 2


def test_iter_attachment_records_resumes_from_offset(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    first_line = _make_success_line(tool_use_id="toolu_a")
    second_line = _make_success_line(tool_use_id="toolu_b")
    jsonl_file.write_text(first_line + "\n" + second_line + "\n", encoding="utf-8")
    first_line_byte_length = len((first_line + "\n").encode("utf-8"))

    all_parsed_records = list(
        hook_log_extractor.iter_attachment_records_from_file(
            str(jsonl_file),
            start_offset=first_line_byte_length,
        ),
    )

    assert len(all_parsed_records) == 1
    assert all_parsed_records[0][0]["attachment"]["toolUseID"] == "toolu_b"


def test_iter_attachment_records_ignores_malformed_json(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    lines = [
        "{this is not json",
        _make_success_line(),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    all_parsed_records = list(
        hook_log_extractor.iter_attachment_records_from_file(
            str(jsonl_file), start_offset=0
        ),
    )

    assert len(all_parsed_records) == 1


def test_load_offsets_returns_empty_when_file_missing(tmp_path: Path) -> None:
    missing_state_file = tmp_path / "does_not_exist.json"
    assert hook_log_extractor.load_offsets(str(missing_state_file)) == {}


def test_save_and_load_offsets_round_trips(tmp_path: Path) -> None:
    state_file = tmp_path / "nested" / "state.json"
    original_offset_by_path = {"C:/foo.jsonl": 100, "C:/bar.jsonl": 250}
    hook_log_extractor.save_offsets(str(state_file), original_offset_by_path)
    round_tripped = hook_log_extractor.load_offsets(str(state_file))
    assert round_tripped == original_offset_by_path


def test_insert_rows_batches_uses_execute_values_or_executemany() -> None:
    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    all_rows = [
        {
            "event_timestamp": "2026-04-24T13:32:07.978Z",
            "session_id": "s1",
            "cwd": "c",
            "git_branch": "b",
            "hook_event": "PreToolUse",
            "hook_name": "PreToolUse:Bash",
            "hook_category": "blocking",
            "script_path": "s",
            "tool_name": "Bash",
            "tool_use_id": "t",
            "outcome": OUTCOME_SUCCESS,
            "exit_code": 0,
            "duration_ms": 1,
            "command_excerpt": "cmd",
            "stdout_excerpt": "out",
            "stderr_excerpt": "",
            "source_jsonl_path": "/p.jsonl",
            "source_line_number": each_line_number,
        }
        for each_line_number in range(1, 4)
    ]

    hook_log_extractor.insert_rows_batch(fake_connection, all_rows)

    assert fake_cursor.executemany.called or fake_cursor.execute.called


def test_run_full_extraction_advances_offset(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")

    state_file = tmp_path / "offsets.json"

    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = MagicMock()

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert exit_code == 0
    saved_offsets = hook_log_extractor.load_offsets(str(state_file))
    assert str(jsonl_file) in saved_offsets
    assert saved_offsets[str(jsonl_file)] > 0


def test_run_full_extraction_idempotent_when_offset_at_end(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    success_line = _make_success_line() + "\n"
    jsonl_file.write_text(success_line, encoding="utf-8")

    state_file = tmp_path / "offsets.json"
    hook_log_extractor.save_offsets(
        str(state_file),
        {str(jsonl_file): len(success_line.encode("utf-8"))},
    )

    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert exit_code == 0
    assert not fake_cursor.executemany.called


def test_run_full_rebuild_clears_offsets_and_truncates(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")

    state_file = tmp_path / "offsets.json"
    hook_log_extractor.save_offsets(str(state_file), {str(jsonl_file): 99999})

    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=True,
        )

    assert exit_code == 0
    all_executed_statements = [
        each_call.args[0] for each_call in fake_cursor.execute.call_args_list
    ]
    assert any(
        "TRUNCATE" in each_statement.upper()
        for each_statement in all_executed_statements
    )
    saved_offsets_after_rebuild = hook_log_extractor.load_offsets(str(state_file))
    assert saved_offsets_after_rebuild.get(str(jsonl_file), 0) > 0


def test_offline_fallback_writes_one_log_line_when_connect_fails(
    tmp_path: Path,
) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")

    state_file = tmp_path / "offsets.json"
    warning_log = tmp_path / "hook-extractor.log"

    class _FakeOperationalError(Exception):
        pass

    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise _FakeOperationalError("boom")

    with (
        patch.object(hook_log_extractor, "connect_to_neon", side_effect=_raise),
        patch.object(hook_log_extractor, "is_operational_error", return_value=True),
        patch.object(hook_log_extractor, "OFFLINE_WARNING_LOG_PATH", str(warning_log)),
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert exit_code == 0
    log_contents = warning_log.read_text(encoding="utf-8")
    assert len(log_contents.strip().splitlines()) == 1


def test_tool_name_extracted_from_hook_name_prefix() -> None:
    assert hook_log_extractor.extract_tool_name("PreToolUse:Bash") == "Bash"
    assert hook_log_extractor.extract_tool_name("PreToolUse:Write|Edit") == "Write|Edit"
    assert hook_log_extractor.extract_tool_name("SessionStart") is None
    assert hook_log_extractor.extract_tool_name("UserPromptSubmit") is None


def test_run_summary_prints_no_new_blocks_when_cursor_empty(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = []
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        exit_code = hook_log_extractor.run_summary()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No new blocks since last run." in captured.out


def test_run_summary_prints_table_when_rows_returned(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = [
        ("content_search_to_zoekt_redirector.py", "blocking", 7, "Bash(grep foo)"),
    ]
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        exit_code = hook_log_extractor.run_summary()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "content_search_to_zoekt_redirector.py" in captured.out
    assert "blocking" in captured.out
    assert "7" in captured.out
