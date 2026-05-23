"""Behavior tests for the fix_push_gate_stop_verifier Stop hook.

The vouching decision and block emission run against real data (real JSON
files, a real stream). main's allow-paths are driven through real stdin. The
full re-run-and-block path needs a live PR for gh pr view and the installed
gate, so it is verified by a real run during PR-3 acceptance rather than with
mocks.
"""

import importlib.util
import io
import json
import pathlib
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "fix_push_gate_stop_verifier",
    _HOOK_DIR / "fix_push_gate_stop_verifier.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

_head_is_vouched = hook_module._head_is_vouched
_emit_block = hook_module._emit_block
_GATE_RESULT_FILENAME_TEMPLATE = hook_module.GATE_RESULT_FILENAME_TEMPLATE


def _write_gate_result(tmp_path: pathlib.Path, pr_number: int, passed: bool, head_sha: str) -> None:
    gate_result_path = tmp_path / _GATE_RESULT_FILENAME_TEMPLATE.format(number=pr_number)
    gate_result_path.write_text(
        json.dumps(
            {
                "passed": passed,
                "head_sha": head_sha,
                "base_ref": "worktree-base",
                "checked_at": "2026-05-23T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )


def _run_main_with(payload: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()
    return int(exit_info.value.code)


def test_head_is_vouched_when_passing_record_matches(tmp_path: pathlib.Path) -> None:
    _write_gate_result(tmp_path, 484, True, "abc123")
    assert _head_is_vouched(tmp_path, 484, "abc123") is True


def test_head_is_not_vouched_when_sha_differs(tmp_path: pathlib.Path) -> None:
    _write_gate_result(tmp_path, 484, True, "abc123")
    assert _head_is_vouched(tmp_path, 484, "def456") is False


def test_head_is_not_vouched_when_record_failed(tmp_path: pathlib.Path) -> None:
    _write_gate_result(tmp_path, 484, False, "abc123")
    assert _head_is_vouched(tmp_path, 484, "abc123") is False


def test_head_is_not_vouched_when_file_missing(tmp_path: pathlib.Path) -> None:
    assert _head_is_vouched(tmp_path, 484, "abc123") is False


def test_emit_block_writes_block_decision() -> None:
    buffer = io.StringIO()
    _emit_block("a reason", buffer)
    emitted = json.loads(buffer.getvalue())
    assert emitted["decision"] == "block"
    assert emitted["reason"] == "a reason"
    assert emitted["suppressOutput"] is True


def test_main_allows_when_stop_hook_active(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_main_with({"stop_hook_active": True}, monkeypatch) == 0
    assert capsys.readouterr().out.strip() == ""


def test_main_allows_outside_git_repo(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    assert _run_main_with({}, monkeypatch) == 0
    assert capsys.readouterr().out.strip() == ""
