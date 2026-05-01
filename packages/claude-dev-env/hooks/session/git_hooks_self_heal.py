#!/usr/bin/env python3
"""SessionStart hook: ensure git-hooks install is intact, re-run installer if not.

Runs at every Claude Code session start. Cheap fast-path checks ``core.hooksPath``
and the three shim filenames; only spawns ``node bin/git_hooks_installer.mjs``
when the install has been damaged or never run. Silent on the happy path so
session startup stays quiet.

Respects external git-hook managers (husky, lefthook): if ``core.hooksPath``
points anywhere other than the claude-dev-env target, the hook exits without
disturbing the user's configuration.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree_directory = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree_directory)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.dynamic_stderr_handler import DynamicStderrHandler  # noqa: E402
from config.git_hooks_self_heal_constants import (  # noqa: E402
    ALL_EXPECTED_HOOKS_PATH_SEGMENTS_FROM_HOME,
    ALL_INSTALLER_PATH_SEGMENTS_FROM_PLUGIN_ROOT,
    ALL_KNOWN_GIT_HOOK_FILENAMES,
    CORE_HOOKS_PATH_CONFIG_KEY,
    INSTALLER_FAILURE_MESSAGE,
    INSTALLER_TIMEOUT_SECONDS,
    LOGGER_FORMATTER_PATTERN,
    LOGGER_NAME,
    NODE_EXECUTABLE_NAME,
)


_logger = logging.getLogger(LOGGER_NAME)
if not _logger.handlers:
    _stderr_handler = DynamicStderrHandler()
    _stderr_handler.setFormatter(logging.Formatter(LOGGER_FORMATTER_PATTERN))
    _logger.addHandler(_stderr_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def user_home_directory() -> Path:
    """Return the current user's home directory; isolated for test override."""
    return Path.home()


def expected_hooks_directory(home_directory: Path) -> Path:
    """Compose the canonical claude-dev-env git-hooks directory under ``home``."""
    return home_directory.joinpath(*ALL_EXPECTED_HOOKS_PATH_SEGMENTS_FROM_HOME)


def read_global_hooks_path() -> str:
    """Read ``git config --global --get core.hooksPath`` as a stripped string.

    Returns the empty string when the setting is unset, to match the hook's
    "no global override" code path.
    """
    completed = subprocess.run(
        ["git", "config", "--global", "--get", CORE_HOOKS_PATH_CONFIG_KEY],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip()


def all_shims_present(hooks_directory: Path) -> bool:
    return all(
        (hooks_directory / each_filename).is_file()
        for each_filename in ALL_KNOWN_GIT_HOOK_FILENAMES
    )


def installer_script_path() -> Path:
    plugin_root = Path(__file__).resolve().parents[2]
    return plugin_root.joinpath(*ALL_INSTALLER_PATH_SEGMENTS_FROM_PLUGIN_ROOT)


def invoke_installer() -> int:
    """Run the JS installer; return its exit code (non-zero indicates failure)."""
    try:
        completed = subprocess.run(
            [NODE_EXECUTABLE_NAME, str(installer_script_path())],
            capture_output=True,
            text=True,
            check=False,
            timeout=INSTALLER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as installer_error:
        _logger.error(INSTALLER_FAILURE_MESSAGE.format(error=installer_error))
        return 1
    return completed.returncode


def _paths_equal(left_path: Path, right_path: Path) -> bool:
    return Path(str(left_path)) == Path(str(right_path))


def main() -> None:
    home_directory = user_home_directory()
    expected_directory = expected_hooks_directory(home_directory)
    configured_hooks_path = read_global_hooks_path()

    if configured_hooks_path == "":
        installer_exit_code = invoke_installer()
        if installer_exit_code != 0:
            _logger.error(
                INSTALLER_FAILURE_MESSAGE.format(
                    error=f"installer exited {installer_exit_code}"
                )
            )
        sys.exit(0)

    configured_directory = Path(configured_hooks_path)
    if not _paths_equal(configured_directory, expected_directory):
        sys.exit(0)

    if all_shims_present(expected_directory):
        sys.exit(0)

    installer_exit_code = invoke_installer()
    if installer_exit_code != 0:
        _logger.error(
            INSTALLER_FAILURE_MESSAGE.format(
                error=f"installer exited {installer_exit_code}"
            )
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
