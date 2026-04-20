"""Root pytest configuration: keeps the repo-root ``config`` package resolvable.

Two problems to defeat:

1. **Missing-sys.path (CI full pytest):** ``pytest`` under ``--import-mode=importlib``
   does not add the repo root to ``sys.path``. ``.github/scripts/sync_ai_rules.py``
   does ``from config.sync_ai_rules_paths import ...`` which requires the repo root
   on ``sys.path``. Inserting at conftest-module-load time ensures it is present
   before any test module is imported.

2. **Hook-local shadow (local full pytest):** ``packages/claude-dev-env/hooks/git-hooks/config.py``
   is a flat module with the same import name as the repo-root ``config/`` package.
   When hook-local tests collect first (alphabetical), they cache the flat module in
   ``sys.modules`` and insert ``git-hooks/`` into ``sys.path``. ``pytest_collectstart``
   evicts that cache and restores precedence just before
   ``tests/test_sync_ai_rules.py`` is imported.

In production the two imports never overlap: the git-hook shim runs
``pre_push.py`` / ``pre_commit.py`` as scripts with only ``git-hooks/`` on
``sys.path``, and the sync listener runs ``sync_ai_rules.py`` with only the repo
root on ``sys.path``. Only pytest's single-process collection mixes them.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest


_SYNC_AI_RULES_TEST_FILENAME = "test_sync_ai_rules.py"
_REPOSITORY_ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
_HOOK_LOCAL_DIRECTORY_PATH = os.path.join(
    _REPOSITORY_ROOT_PATH, "packages", "claude-dev-env", "hooks", "git-hooks",
)


if _REPOSITORY_ROOT_PATH not in sys.path:
    sys.path.insert(0, _REPOSITORY_ROOT_PATH)


def pytest_collectstart(collector: pytest.Collector) -> None:
    collected_path = getattr(collector, "path", None)
    if collected_path is None:
        return
    if collected_path.name != _SYNC_AI_RULES_TEST_FILENAME:
        return
    sys.modules.pop("config", None)
    sys.modules.pop("config.sync_ai_rules_paths", None)
    importlib.invalidate_caches()
    while _HOOK_LOCAL_DIRECTORY_PATH in sys.path:
        sys.path.remove(_HOOK_LOCAL_DIRECTORY_PATH)
    if _REPOSITORY_ROOT_PATH not in sys.path:
        sys.path.insert(0, _REPOSITORY_ROOT_PATH)
