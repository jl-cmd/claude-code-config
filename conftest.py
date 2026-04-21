"""Root pytest configuration: evicts conflicting ``config`` imports during collection.

Three different objects share the top-level name ``config``:

- Repository package ``config/`` (for example ``config.sync_ai_rules_paths``).
- ``packages/claude-dev-env/hooks/config/`` (hook messages and shared hook tests).
- ``packages/claude-dev-env/hooks/git-hooks/config.py`` (flat constants for shims).

``pytest.ini`` puts ``packages/claude-dev-env/hooks`` before ``.`` on ``pythonpath``
so hook tests resolve ``hooks/config`` instead of the repository package. Only one
binding can live in ``sys.modules["config"]`` at a time, so ``pytest_collectstart``
evicts it before each incompatible test file is collected.

``sync_ai_rules.py`` only prepends the repository root when it is not already on
``sys.path``; with ``hooks`` ahead of ``.``, that insert is skipped and ``config``
would incorrectly resolve to ``hooks/config``. For ``tests/test_sync_ai_rules.py``
collection only, this module removes the hooks tree from ``sys.path`` and evicts
``config``; the next ``pytest_collectstart`` call re-adds the hooks directory so
later collection and tests keep working.

In production the imports do not overlap: shims prepend only ``git-hooks/``, and
the sync script prepends only the repository root. Only pytest mixes them.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_SYNC_AI_RULES_TEST_FILENAME = "test_sync_ai_rules.py"
_REPOSITORY_ROOT_PATH = Path(__file__).resolve().parent
_GIT_HOOKS_DIRECTORY_PATH = _REPOSITORY_ROOT_PATH / "packages" / "claude-dev-env" / "hooks" / "git-hooks"
_HOOKS_ROOT_DIRECTORY_PATH = _REPOSITORY_ROOT_PATH / "packages" / "claude-dev-env" / "hooks"


def _evict_config_module() -> None:
    sys.modules.pop("config", None)
    sys.modules.pop("config.sync_ai_rules_paths", None)
    importlib.invalidate_caches()


def _resolved_path_matches_sys_path_entry(directory_path: Path, entry: str) -> bool:
    try:
        return Path(entry).resolve() == directory_path.resolve()
    except OSError:
        return False


def _remove_path_if_present(directory_path: Path) -> None:
    target = directory_path.resolve()
    sys.path[:] = [
        entry for entry in sys.path if not _resolved_path_matches_sys_path_entry(target, entry)
    ]


def _hooks_root_is_on_sys_path() -> bool:
    target = _HOOKS_ROOT_DIRECTORY_PATH.resolve()
    return any(_resolved_path_matches_sys_path_entry(target, entry) for entry in sys.path)


def _ensure_hooks_root_on_sys_path() -> None:
    if _hooks_root_is_on_sys_path():
        return
    sys.path.insert(0, str(_HOOKS_ROOT_DIRECTORY_PATH.resolve()))


def pytest_collectstart(collector: pytest.Collector) -> None:
    collected_path = getattr(collector, "path", None)
    if collected_path is None:
        return
    resolved_collected_path = collected_path.resolve()

    if collected_path.name == _SYNC_AI_RULES_TEST_FILENAME:
        _evict_config_module()
        _remove_path_if_present(_GIT_HOOKS_DIRECTORY_PATH)
        _remove_path_if_present(_HOOKS_ROOT_DIRECTORY_PATH)
        return

    _ensure_hooks_root_on_sys_path()

    try:
        resolved_collected_path.relative_to(_GIT_HOOKS_DIRECTORY_PATH.resolve())
    except ValueError:
        pass
    else:
        if collected_path.name.startswith("test_"):
            _evict_config_module()
        return

    try:
        resolved_collected_path.relative_to(_HOOKS_ROOT_DIRECTORY_PATH.resolve())
    except ValueError:
        return

    if collected_path.name.startswith("test_") or collected_path.name.startswith(
        "should_"
    ):
        _evict_config_module()
