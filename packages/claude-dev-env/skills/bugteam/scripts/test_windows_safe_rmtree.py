"""Tests for windows_safe_rmtree."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from windows_safe_rmtree import main, remove_tree


def test_remove_tree_deletes_plain_directory(tmp_path: Path) -> None:
    target = tmp_path / "victim"
    target.mkdir()
    (target / "file.txt").write_text("payload", encoding="utf-8")
    remove_tree(str(target))
    assert not target.exists()


def test_remove_tree_handles_read_only_file(tmp_path: Path) -> None:
    target = tmp_path / "victim"
    target.mkdir()
    locked_file = target / "locked.txt"
    locked_file.write_text("payload", encoding="utf-8")
    os.chmod(locked_file, stat.S_IREAD)
    remove_tree(str(target))
    assert not target.exists()


def test_remove_tree_swallows_missing_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "does-not-exist"
    remove_tree(str(missing_path))


def test_main_returns_zero_on_success(tmp_path: Path) -> None:
    target = tmp_path / "victim"
    target.mkdir()
    exit_code = main(["windows_safe_rmtree.py", str(target)])
    assert exit_code == 0
    assert not target.exists()


def test_main_returns_usage_exit_code_when_argv_count_wrong(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["windows_safe_rmtree.py"])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "usage" in captured.err.lower()
