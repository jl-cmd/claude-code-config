"""Centralized timing configuration for sweep_empty_dirs.

All module-level scalar constants live here per the repo's ``constants-location``
rule. Import into the script and bind local aliases where needed.
"""

DEFAULT_AGE_SECONDS: int = 120
"""Minimum age before an empty directory is eligible for deletion."""

DEFAULT_POLL_INTERVAL: int = 30
"""Seconds between sweep passes in continuous-watch mode."""
