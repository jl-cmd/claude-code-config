"""Constants for the git-hooks SessionStart self-healer.

Co-located with the other ``hooks/config/*_constants.py`` modules so that
``git_hooks_self_heal.py`` and its tests can import shared values from one
place rather than re-declaring them at file scope.
"""

from __future__ import annotations


ALL_KNOWN_GIT_HOOK_FILENAMES: tuple[str, ...] = (
    "pre-commit",
    "pre-push",
    "post-commit",
)
ALL_EXPECTED_HOOKS_PATH_SEGMENTS_FROM_HOME: tuple[str, ...] = (
    ".claude",
    "hooks",
    "git-hooks",
)
ALL_INSTALLER_PATH_SEGMENTS_FROM_PLUGIN_ROOT: tuple[str, ...] = (
    "bin",
    "git_hooks_installer.mjs",
)
CORE_HOOKS_PATH_CONFIG_KEY: str = "core.hooksPath"
NODE_EXECUTABLE_NAME: str = "node"
INSTALLER_TIMEOUT_SECONDS: int = 10
INSTALLER_FAILURE_MESSAGE: str = "claude-dev-env: git-hooks self-heal failed: {error}"
LOGGER_NAME: str = "git_hooks_self_heal"
LOGGER_FORMATTER_PATTERN: str = "%(name)s: %(message)s"
