"""Tunable constants for the destructive_command_blocker hook.

The autoconverge convergence workflow suspends destructive blocking for the
duration of a run by writing a marker file. This window bounds how long a marker
grants the bypass before the hook treats it as stale, removes it, and re-arms the
guard.
"""

AUTOCONVERGE_DESTRUCTIVE_BYPASS_FRESHNESS_WINDOW_SECONDS: int = 7200
