#!/usr/bin/env python3
"""PreToolUse hook: block @cursor or @copilot mentions in add_issue_comment body.

Bugbot trigger requires exactly ``bugbot run`` with no other text. Copilot review
requires the GitHub REST API endpoint, not an issue comment mention. This hook
catches both mistakes and returns the correct procedure for each.
"""

import json
import sys

from config.bot_mention_comment_blocker_constants import (
    COPILOT_MENTION_TOKEN,
    CORRECTIVE_MESSAGE_COPILOT,
    CORRECTIVE_MESSAGE_CURSOR,
    CURSOR_MENTION_TOKEN,
    TOOL_NAME,
)


def _body_contains_token(body: str, token: str) -> bool:
    return token.lower() in body.lower()


def _detect_bot_mention(body: str) -> str | None:
    """Return corrective message if body contains a blocked mention, else None."""
    copilot_mention_token = COPILOT_MENTION_TOKEN
    corrective_message_copilot = CORRECTIVE_MESSAGE_COPILOT
    cursor_mention_token = CURSOR_MENTION_TOKEN
    corrective_message_cursor = CORRECTIVE_MESSAGE_CURSOR
    if _body_contains_token(body, copilot_mention_token):
        return corrective_message_copilot
    if _body_contains_token(body, cursor_mention_token):
        return corrective_message_cursor
    return None


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name_value = TOOL_NAME
    if hook_input.get("tool_name", "") != tool_name_value:
        sys.exit(0)

    body = hook_input.get("tool_input", {}).get("body", "")
    if not body:
        sys.exit(0)

    corrective_message = _detect_bot_mention(body)
    if corrective_message is None:
        sys.exit(0)

    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": corrective_message,
        }
    }
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
