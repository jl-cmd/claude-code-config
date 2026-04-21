"""Shared path-classification helpers for the blocking hook layer.

Both ``code_rules_enforcer.py`` (pre-write gate) and
``validators/exempt_paths.py`` (pre-push validator) need to agree on what
constitutes a config file. This module is the single implementation; both
import ``is_config_file`` from here so they cannot drift apart.

``validators/exempt_paths.py`` re-exports this function and documents that
the canonical implementation lives here.
"""

from __future__ import annotations

from pathlib import Path


def is_config_file(file_path: str) -> bool:
    """Return True when the path points to a config file.

    A file is considered a config file when its parent directory segment is
    literally ``config`` (any depth), or when its filename is ``settings.py``
    (with or without a parent directory prefix). Filename-only matches such as
    ``scripts/db/config.py`` or ``lib/myconfig.py`` return False because the
    directory segment must be the one named ``config``, not the filename stem.
    """
    normalized = file_path.replace("\\", "/").lower()
    if normalized.endswith("/settings.py") or normalized == "settings.py":
        return True
    path_parts = Path(normalized).parts
    return "config" in path_parts[:-1]
