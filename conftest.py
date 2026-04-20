"""Root pytest hooks that keep hook-local and repo-root ``config`` modules isolated.

``packages/claude-dev-env/hooks/git-hooks/config.py`` (flat module) and the
repo-root ``config/`` package share the import name ``config``. During a full
``pytest`` run the hook-local tests collect first (alphabetical order);
``test_config.py`` and ``test_pre_push.py`` insert ``git-hooks/`` into
``sys.path`` and cache the flat ``config`` module in ``sys.modules``.

When collection reaches ``tests/test_sync_ai_rules.py``, importing
``.github/scripts/sync_ai_rules.py`` then does
``from config.sync_ai_rules_paths import ...``. Python resolves ``config``
against the cached flat module first and raises ``'config' is not a package``.

``pytest_collectstart`` runs before each file is imported for collection, so
evicting the hook-local ``config`` binding, removing the hook-local directory
from ``sys.path``, and ensuring the repo root precedes it forces Python to
resolve ``config`` against the package.

In production these imports never overlap: the git-hook shim runs
``pre_push.py`` / ``pre_commit.py`` as scripts with only ``git-hooks/`` on
``sys.path``, and the sync listener runs ``sync_ai_rules.py`` with only the
repo root on ``sys.path``. Only pytest's single-process collection mixes them.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest


_SYNC_AI_RULES_TEST_FILENAME = "test_sync_ai_rules.py"


def pytest_collectstart(collector: pytest.Collector) -> None:
    collected_file_path = getattr(collector, "fspath", None)
    if collected_file_path is None:
        return
    if os.path.basename(str(collected_file_path)) != _SYNC_AI_RULES_TEST_FILENAME:
        return
    sys.modules.pop("config", None)
    sys.modules.pop("config.sync_ai_rules_paths", None)
    importlib.invalidate_caches()
    repository_root_path = os.path.dirname(os.path.abspath(__file__))
    hook_local_directory = os.path.join(
        repository_root_path, "packages", "claude-dev-env", "hooks", "git-hooks",
    )
    while hook_local_directory in sys.path:
        sys.path.remove(hook_local_directory)
    if repository_root_path not in sys.path:
        sys.path.insert(0, repository_root_path)
