"""Tests for sweep_empty_dirs script behaviors."""

import argparse
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.sweep_empty_dirs import _build_parser, _positive_int, sweep


def test_positive_int_accepts_valid_value() -> None:
    """_positive_int accepts integers >= 1."""
    assert _positive_int("5") == 5


def test_positive_int_accepts_minimum_value() -> None:
    """_positive_int accepts exactly 1."""
    assert _positive_int("1") == 1


def test_positive_int_rejects_zero() -> None:
    """_positive_int raises for 0."""
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_int("0")


def test_positive_int_rejects_negative() -> None:
    """_positive_int raises for negative values."""
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_int("-1")


def test_build_parser_sets_age_default_from_timing_config() -> None:
    """_build_parser uses DEFAULT_AGE_SECONDS from config.timing as --age default."""
    parser = _build_parser()
    default_age = parser.get_default("age")
    assert isinstance(default_age, int)
    assert default_age > 0


def test_build_parser_sets_interval_default_from_timing_config() -> None:
    """_build_parser uses DEFAULT_POLL_INTERVAL from config.timing as --interval default."""
    parser = _build_parser()
    default_interval = parser.get_default("interval")
    assert isinstance(default_interval, int)
    assert default_interval > 0


def test_sweep_removes_empty_directory(tmp_path: Path) -> None:
    """sweep removes an empty directory older than the age threshold."""
    empty_dir = tmp_path / "empty_old"
    empty_dir.mkdir()

    sweep(str(tmp_path), min_age_seconds=0)

    assert not empty_dir.exists()


def test_sweep_preserves_non_empty_directory(tmp_path: Path) -> None:
    """sweep does not remove a directory containing files."""
    non_empty_dir = tmp_path / "has_files"
    non_empty_dir.mkdir()
    (non_empty_dir / "some_file.txt").write_text("content")

    sweep(str(tmp_path), min_age_seconds=0)

    assert non_empty_dir.exists()


def test_sweep_preserves_root_directory(tmp_path: Path) -> None:
    """sweep never removes the root directory itself."""
    sub_dir = tmp_path / "subdir"
    sub_dir.mkdir()

    sweep(str(tmp_path), min_age_seconds=0)

    assert tmp_path.exists()


def test_sweep_removes_nested_empty_dirs(tmp_path: Path) -> None:
    """sweep removes nested empty directories bottom-up."""
    nested = tmp_path / "level1" / "level2" / "level3"
    nested.mkdir(parents=True)

    sweep(str(tmp_path), min_age_seconds=0)

    assert not nested.exists()
    assert not (tmp_path / "level1" / "level2").exists()
    assert not (tmp_path / "level1").exists()


def test_sweep_removes_only_old_enough_directories(tmp_path: Path) -> None:
    """sweep does not remove directories newer than the age threshold."""
    young_dir = tmp_path / "young"
    young_dir.mkdir()

    sweep(str(tmp_path), min_age_seconds=9999999)

    assert young_dir.exists()


def test_sweep_returns_list_of_removed_directories(tmp_path: Path) -> None:
    """sweep returns the paths of directories it removed."""
    old_dir = tmp_path / "old_empty"
    old_dir.mkdir()

    removed = sweep(str(tmp_path), min_age_seconds=0)

    assert old_dir.name in [Path(p).name for p in removed]
