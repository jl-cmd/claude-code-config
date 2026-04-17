"""Shared configuration for the sync-claude-workflow package."""

from __future__ import annotations

CANONICAL_WORKFLOW_PATH_IN_THIS_REPO: str = ".github/workflows/claude.yml"
TARGET_WORKFLOW_PATH: str = ".github/workflows/claude.yml"
TARGET_DEFAULT_BRANCH: str = "main"
SYNC_COMMIT_MESSAGE: str = "chore(workflows): sync claude.yml from claude-code-config"

HTTP_NOT_FOUND_STATUS_INDICATORS: tuple[str, ...] = ("Not Found", "404")

TARGET_REPOS: tuple[str, ...] = (
    "JonEcho/babysit-pr",
    "JonEcho/theme-asset-db",
    "JonEcho/llm-settings",
    "JonEcho/theme-skills",
    "JonEcho/python-automation",
    "jl-cmd/prompt-generator",
    "jl-cmd/redlib",
)

EXIT_CODE_SUCCESS: int = 0
EXIT_CODE_PARTIAL_FAILURE: int = 1
