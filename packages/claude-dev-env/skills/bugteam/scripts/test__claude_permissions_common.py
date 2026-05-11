"""TDD-pair tests for the underscore-prefixed _claude_permissions_common module.

The TDD enforcer matches a production filename ``X.py`` to ``test_X.py``;
``_claude_permissions_common.py`` carries a leading underscore that the
enforcer treats as part of the name. This file's tests are the canonical
match. The broader behavioral suite continues to live alongside, in
``test_claude_permissions_common.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

import _claude_permissions_common as common_module


def test_write_atomically_with_mode_releases_fd_when_fdopen_raises(
    tmp_path: Path,
) -> None:
    """A failure inside os.fdopen must close the raw file descriptor."""
    target_path = tmp_path / "settings.json.tmp"
    with patch.object(
        common_module.os, "fdopen", side_effect=MemoryError("fdopen failure")
    ):
        with pytest.raises(MemoryError):
            common_module.write_atomically_with_mode(
                target_path, "payload", file_mode=0o600
            )


def test_get_mode_to_preserve_returns_existing_file_mode(
    tmp_path: Path,
) -> None:
    """When the file exists, the actual filesystem mode must be returned (not the default)."""
    target_path = tmp_path / "settings.json"
    target_path.write_text("{}", encoding="utf-8")
    actual_filesystem_mode = target_path.stat().st_mode & 0o777
    returned_mode = common_module.get_mode_to_preserve(target_path)
    assert returned_mode == actual_filesystem_mode


def test_write_atomically_with_mode_raises_oserror_when_open_fails(
    tmp_path: Path,
) -> None:
    """OSError from os.open must propagate (no fd leak path to test here)."""
    target_path = tmp_path / "subdirectory" / "missing" / "settings.json.tmp"
    with pytest.raises(OSError):
        common_module.write_atomically_with_mode(
            target_path, "payload", file_mode=0o600
        )
