"""Tests for sweep_empty_dirs.py"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sweep_empty_dirs import sweep  # noqa: E402


_OLD_TIMESTAMP = time.time() - 300


def test_deletes_empty_dir_older_than_threshold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        empty_dir = os.path.join(tmp, "old_empty")
        os.mkdir(empty_dir)

        with patch("os.path.getctime", return_value=_OLD_TIMESTAMP):
            removed = sweep(tmp, min_age_seconds=120)
        assert empty_dir in removed
        assert not os.path.isdir(empty_dir)


def test_skips_empty_dir_newer_than_threshold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fresh_dir = os.path.join(tmp, "fresh_empty")
        os.mkdir(fresh_dir)

        removed = sweep(tmp, min_age_seconds=120)
        assert fresh_dir not in removed
        assert os.path.isdir(fresh_dir)


def test_deletes_nested_empty_dirs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        leaf = os.path.join(tmp, "parent", "child", "leaf")
        os.makedirs(leaf)
        parent_path = os.path.join(tmp, "parent")
        child_path = os.path.join(tmp, "parent", "child")

        def _mock_getctime(directory_path: str) -> float:
            timestamps_by_path = {
                parent_path: _OLD_TIMESTAMP,
                child_path: _OLD_TIMESTAMP,
                leaf: _OLD_TIMESTAMP,
            }
            return timestamps_by_path.get(directory_path, time.time())

        with patch("os.path.getctime", side_effect=_mock_getctime):
            removed = sweep(tmp, min_age_seconds=120)
        assert leaf in removed
        assert child_path in removed
        assert parent_path in removed


def test_empty_root_does_not_crash() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sweep(tmp, min_age_seconds=120)
        assert os.path.isdir(tmp)


def test_skips_dir_when_getctime_raises_os_error() -> None:
    """Sweep must not crash when os.path.getctime raises an unexpected OSError
    (e.g., broken junction point, disconnected network path)."""
    with tempfile.TemporaryDirectory() as tmp:
        problem_dir = os.path.join(tmp, "broken")
        os.mkdir(problem_dir)

        original_getctime = os.path.getctime

        def _failing_getctime(path: str) -> float:
            if "broken" in path:
                raise OSError("simulated broken junction")
            return original_getctime(path)

        with patch("os.path.getctime", side_effect=_failing_getctime):
            removed = sweep(tmp, min_age_seconds=120)

        assert problem_dir not in removed
        assert os.path.isdir(problem_dir)
