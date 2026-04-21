"""Root pytest configuration: evicts hook-local ``config`` shadows before importing ``test_sync_ai_rules.py``.

``packages/claude-dev-env/hooks/git-hooks/config.py`` is a flat module with the
same import name as the repo-root ``config/`` package. During a full local
pytest run, hook-local tests collect first (alphabetical order);
``test_config.py`` and ``test_pre_push.py`` insert ``git-hooks/`` into
``sys.path`` and cache the flat module in ``sys.modules``.

When ``pytest.ini`` lists ``packages/claude-dev-env/hooks`` on ``pythonpath``
before the repo root (so ``tdd_enforcer`` resolves ``config.messages``), the
``hooks/config/`` package also shadows the repo ``config`` package. When
collection reaches ``tests/test_sync_ai_rules.py``, importing
``.github/scripts/sync_ai_rules.py`` then does
``from config.sync_ai_rules_paths import ...``. Python must resolve ``config``
against the repo package, not the hook tree.

``pytest_collectstart`` runs before each file is imported for collection, so
evicting the ``config`` binding, stripping hook paths from ``sys.path``, and
prepending the repository root forces the correct package for that file.

The ``sys.path`` baseline is established via ``pytest.ini``'s ``pythonpath``;
targeted runs that do not collect conflicting modules do not rely on this hook.

In production the two imports never overlap: the git-hook shim runs
``pre_push.py`` / ``pre_commit.py`` as scripts with only ``git-hooks/`` on
``sys.path``, and the sync listener runs ``sync_ai_rules.py`` with only the
repo root on ``sys.path``. Only pytest's single-process collection mixes them.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


_SYNC_AI_RULES_TEST_FILENAME = "test_sync_ai_rules.py"


def pytest_collectstart(collector: pytest.Collector) -> None:
    collected_path = getattr(collector, "path", None)
    if collected_path is None:
        return
    if collected_path.name != _SYNC_AI_RULES_TEST_FILENAME:
        return
    sys.modules.pop("config", None)
    sys.modules.pop("config.sync_ai_rules_paths", None)
    importlib.invalidate_caches()
    repository_root_path = Path(__file__).resolve().parent
    git_hooks_directory_string = str(
        repository_root_path.joinpath(
            "packages", "claude-dev-env", "hooks", "git-hooks"
        )
    )
    hook_tree_root_string = str(
        repository_root_path.joinpath("packages", "claude-dev-env", "hooks")
    )
    for each_hook_path_string in (
        git_hooks_directory_string,
        hook_tree_root_string,
    ):
        while each_hook_path_string in sys.path:
            sys.path.remove(each_hook_path_string)
    repository_root_string = str(repository_root_path)
    while repository_root_string in sys.path:
        sys.path.remove(repository_root_string)
    sys.path.insert(0, repository_root_string)
