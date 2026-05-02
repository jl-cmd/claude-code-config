"""Tests for wait_and_continue: sleep then emit continuation file to stdout."""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _load_module():
    module_path = Path(__file__).parent / "wait_and_continue.py"
    specification = importlib.util.spec_from_file_location("wait_and_continue", module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


wait_and_continue_module = _load_module()


def test_wait_and_continue_prints_file_after_sleep(tmp_path: Path) -> None:
    continuation_path = tmp_path / "inj.txt"
    continuation_path.write_text("next tick payload\nline2", encoding="utf-8")
    buffer = io.StringIO()
    with patch.object(wait_and_continue_module.time, "sleep") as mock_sleep:
        with patch.object(sys, "stdout", buffer):
            wait_and_continue_module.wait_and_continue(
                delay_seconds=270,
                continuation_path=continuation_path,
            )
    mock_sleep.assert_called_once_with(270)
    assert buffer.getvalue() == "next tick payload\nline2\n"


def test_wait_and_continue_cli_prints_file(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    continuation_path = tmp_path / "c.txt"
    continuation_path.write_text("hello", encoding="utf-8")
    fake_argv = [
        "wait_and_continue.py",
        "--delay-seconds",
        "60",
        "--continuation-file",
        str(continuation_path),
    ]
    with patch.object(wait_and_continue_module.time, "sleep"):
        with patch.object(sys, "argv", fake_argv):
            exit_code = wait_and_continue_module.main()
    assert exit_code == 0
    assert capsys.readouterr().out == "hello\n"


def test_wait_and_continue_missing_file_exits_code_two(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.txt"
    fake_argv = [
        "wait_and_continue.py",
        "--delay-seconds",
        "1",
        "--continuation-file",
        str(missing),
    ]
    with patch.object(sys, "argv", fake_argv):
        exit_code = wait_and_continue_module.main()
    assert exit_code == 2


def test_delay_above_cap_exits_code_two(tmp_path: Path) -> None:
    continuation_path = tmp_path / "ok.txt"
    continuation_path.write_text("x", encoding="utf-8")
    fake_argv = [
        "wait_and_continue.py",
        "--delay-seconds",
        "86401",
        "--continuation-file",
        str(continuation_path),
    ]
    with patch.object(sys, "argv", fake_argv):
        exit_code = wait_and_continue_module.main()
    assert exit_code == 2


def test_delay_negative_exits_code_two(tmp_path: Path) -> None:
    continuation_path = tmp_path / "ok.txt"
    continuation_path.write_text("x", encoding="utf-8")
    fake_argv = [
        "wait_and_continue.py",
        "--delay-seconds",
        "-1",
        "--continuation-file",
        str(continuation_path),
    ]
    with patch.object(sys, "argv", fake_argv):
        exit_code = wait_and_continue_module.main()
    assert exit_code == 2


def test_subprocess_invocation_end_to_end(tmp_path: Path) -> None:
    script_path = Path(__file__).parent / "wait_and_continue.py"
    continuation_path = tmp_path / "full.txt"
    continuation_path.write_text("subprocess ok", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--delay-seconds",
            "0",
            "--continuation-file",
            str(continuation_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout == "subprocess ok\n"
