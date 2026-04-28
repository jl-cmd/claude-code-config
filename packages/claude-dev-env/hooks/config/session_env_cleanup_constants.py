"""Configuration constants for the session_env_cleanup SessionStart hook."""

from __future__ import annotations

import os

SESSION_ENV_DIRECTORY = os.path.join(os.path.expanduser("~"), ".claude", "session-env")

SECONDS_PER_DAY = 24 * 60 * 60
STALE_AGE_DAYS = 7
STALE_AGE_SECONDS = STALE_AGE_DAYS * SECONDS_PER_DAY
