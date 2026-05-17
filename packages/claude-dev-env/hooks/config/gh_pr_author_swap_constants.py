"""Configuration constants for the gh-pr-author swap hook pair.

The PreToolUse enforcer (``gh_pr_author_enforcer.py``) auto-switches the
active ``gh`` CLI account to ``GITHUB_DEFAULT_ACCOUNT`` before a
``gh pr create`` invocation, and the PostToolUse companion
(``gh_pr_author_restore.py``) restores the prior account afterwards. The
state file written between the two hooks is keyed per session so parallel
Claude Code sessions cannot stomp on each other's swap state.

``SECONDARY_ACCOUNT_ENV_VAR`` is declared here even though neither hook
in this pair reads it. Sibling hooks and skills that swap *to* the
secondary account (for example, the /bugteam workflow that posts
REQUEST_CHANGES from a non-author identity) read the same env var; this
module is the single source of truth so callers can avoid hardcoding
``"jl-cmd"`` or another login literal.
"""

from __future__ import annotations

import re

REQUIRED_ACCOUNT_ENV_VAR: str = "GITHUB_DEFAULT_ACCOUNT"
SECONDARY_ACCOUNT_ENV_VAR: str = "GITHUB_SECONDARY_ACCOUNT"

BASH_TOOL_NAME: str = "Bash"

GH_PR_CREATE_PATTERN: re.Pattern[str] = re.compile(r"\bgh\s+pr\s+create\b", re.IGNORECASE)
WEB_FLAG_PATTERN: re.Pattern[str] = re.compile(r"(?<!\S)(?:--web|-w)(?!\S)")

ALL_GH_API_USER_COMMAND: tuple[str, ...] = ("gh", "api", "user", "--jq", ".login")
GH_API_USER_TIMEOUT_SECONDS: int = 5

ALL_GH_AUTH_SWITCH_COMMAND_HEAD: tuple[str, ...] = ("gh", "auth", "switch", "--user")
GH_AUTH_SWITCH_TIMEOUT_SECONDS: int = 10

STATE_FILE_PREFIX: str = "gh_pr_author_swap_"
STATE_FILE_SUFFIX: str = ".json"
STATE_FILE_DEFAULT_SESSION_ID: str = "default"

STATE_FILE_ORIGINAL_ACCOUNT_KEY: str = "original_account"
STATE_FILE_PRIMARY_ACCOUNT_KEY: str = "primary_account"
