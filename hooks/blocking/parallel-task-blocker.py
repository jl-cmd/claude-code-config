#!/usr/bin/env python3
"""PreToolUse:Task hook — suggests team orchestration for parallel Task spawning.

Detects parallel Task/Agent calls without team_name and injects a suggestion
into the conversation context. Does NOT block — the tool call proceeds.

Uses atomic file creation (O_CREAT | O_EXCL) to detect concurrent calls.
Lock auto-expires after 3 seconds to avoid false positives on sequential calls.
"""

import json
import os
import sys
import tempfile
import time

LOCK_FILE = os.path.join(tempfile.gettempdir(), "claude-parallel-task-guard.lock")
LOCK_MAX_AGE_SECONDS = 3

SUGGESTION_MESSAGE = (
    "SUGGESTION: Multiple parallel agents detected without team orchestration. "
    "Consider using TeamCreate + team_name for better coordination, "
    "progress tracking, and file ownership management. "
    "This is optional — parallel agents will proceed without it."
)


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name not in ("Task", "Agent"):
        sys.exit(0)

    # Team-orchestrated tasks — no suggestion needed
    if tool_input.get("team_name"):
        sys.exit(0)

    # Clean stale locks (previous turn's lock that wasn't cleaned up)
    try:
        if os.path.exists(LOCK_FILE):
            lock_age = time.time() - os.path.getmtime(LOCK_FILE)
            if lock_age > LOCK_MAX_AGE_SECONDS:
                os.unlink(LOCK_FILE)
    except OSError:
        pass  # Race with another process cleaning — fine

    # Atomic create: only one concurrent caller wins
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(time.time()).encode())
        os.close(fd)
        # First Task in this turn — no suggestion
        sys.exit(0)
    except FileExistsError:
        pass  # Another Task already holds the lock

    # Second+ parallel Task without team → suggest (not block)
    print(SUGGESTION_MESSAGE, file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
