#!/usr/bin/env python3
"""PreToolUse hook: block @cursor or @copilot mentions in add_issue_comment body.

Bugbot trigger requires exactly ``bugbot run`` with no other text. Copilot review
requires the GitHub REST API endpoint, not an issue comment mention. This hook
catches both mistakes and returns the correct procedure for each.
"""

import json
import sys

_TOOL_NAME = "mcp__plugin_github_github__add_issue_comment"

_CURSOR_MENTION_TOKEN = "@cursor"
_COPILOT_MENTION_TOKEN = "@copilot"

_CORRECTIVE_MESSAGE_CURSOR = (
    "BLOCKED [bot-mention]: Invalid comment. "
    "Post exactly ``bugbot run`` with no other text as your issue comment "
    "to trigger Bugbot."
)

_CORRECTIVE_MESSAGE_COPILOT = (
    "BLOCKED [bot-mention]: Invalid comment. "
    "To request a Copilot review, use the GitHub REST API:\n"
    "  gh api --method POST repos/<owner>/<repo>/pulls/<number>/requested_reviewers \\\n"
    "    -f 'reviewers[]=copilot-pull-request-reviewer[bot]'\n"
    "See ~/.claude/skills/pr-converge/reference/convergence-gates.md."
)


def _body_contains_token(body: str, token: str) -> bool:
    return token.lower() in body.lower()


def _detect_bot_mention(body: str) -> str | None:
    """Return corrective message if body contains a blocked mention, else None."""
    if _body_contains_token(body, _COPILOT_MENTION_TOKEN):
        return _CORRECTIVE_MESSAGE_COPILOT
    if _body_contains_token(body, _CURSOR_MENTION_TOKEN):
        return _CORRECTIVE_MESSAGE_CURSOR
    return None


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name != _TOOL_NAME:
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
