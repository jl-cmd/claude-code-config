"""Shared helper for the CLAUDE_REVIEWS_DISABLED opt-out gate.

Both ``skills/bugteam/scripts/bugteam_preflight.py`` and
``_shared/pr-loop/scripts/preflight.py`` consume this helper so the parsing
rules and disabled-token taxonomy live in exactly one place.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_shared_pr_loop_scripts_directory = Path(__file__).resolve().parent
if str(_shared_pr_loop_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_shared_pr_loop_scripts_directory))

from config.reviews_disabled_constants import (
    CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN,
    CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
    CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR,
    EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV,
)


__all__ = [
    "CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN",
    "CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME",
    "CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR",
    "EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV",
    "is_bugteam_disabled_via_env",
]


def is_bugteam_disabled_via_env() -> bool:
    """Check whether CLAUDE_REVIEWS_DISABLED opts the bug-audit family out of running.

    Returns:
        True when the env var contains the literal ``bugteam`` token
        (comma-separated, case-insensitive, whitespace-tolerant).
    """
    raw_value = os.environ.get(CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME, "")
    all_disabled_tokens = frozenset(
        each_raw_token.strip().lower()
        for each_raw_token in raw_value.split(CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR)
        if each_raw_token.strip()
    )
    return CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN in all_disabled_tokens
