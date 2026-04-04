#!/usr/bin/env python3
"""
PreToolUse hook: blocks direct edits to Docker settings files.
Hooks must be added to the Windows settings.json instead.
"""

import json
import sys

BLOCKED_PATHS = [
    "settings-docker.json",
    "settings-docker",
    "docker/settings-docker.json",
    ".claude/docker/settings-docker.json",
]


def main() -> None:
    try:
        stdin_data = sys.stdin.read()
        hook_input = json.loads(stdin_data)
        tool_input = hook_input.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        for blocked in BLOCKED_PATHS:
            if file_path.endswith(blocked):
                message = "BLOCKED: Docker settings edit denied. Edit your user settings.json instead."
                result = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": message
                    }
                }
                print(json.dumps(result))
                sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        pass


if __name__ == "__main__":
    main()
