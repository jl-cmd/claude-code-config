"""Tests for exempt_paths path-classification helpers.

Covers the is_config_file() contract: only files whose parent directory
segment is literally 'config' should match. A filename of 'config.py'
outside a config/ directory must NOT match.
"""

from __future__ import annotations

from .exempt_paths import is_config_file


def test_should_exempt_file_inside_config_directory() -> None:
    assert is_config_file("project/config/constants.py") is True


def test_should_exempt_file_inside_nested_config_directory() -> None:
    assert is_config_file("packages/myapp/config/timing.py") is True


def test_should_not_exempt_file_named_config_dot_py_outside_config_dir() -> None:
    assert is_config_file("scripts/db/config.py") is False


def test_should_not_exempt_file_with_config_in_filename_only() -> None:
    assert is_config_file("src/app_config.py") is False


def test_should_not_exempt_file_with_config_in_parent_partial_match() -> None:
    assert is_config_file("src/reconfigured/constants.py") is False


def test_should_exempt_settings_py_by_filename() -> None:
    assert is_config_file("any/path/settings.py") is True


def test_should_exempt_windows_path_inside_config_directory() -> None:
    assert is_config_file("packages\\myapp\\config\\timing.py") is True
