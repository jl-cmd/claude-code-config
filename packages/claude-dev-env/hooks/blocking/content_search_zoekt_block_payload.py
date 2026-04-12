from typing import Final

DESTRUCTIVE_GATE_LABEL_PREFIX: Final[str] = "[destructive-gate]"


def build_block_payload(brief_label: str, full_reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
        },
        "decision": "block",
        "reason": full_reason,
        "systemMessage": f"{DESTRUCTIVE_GATE_LABEL_PREFIX} {brief_label}",
        "suppressOutput": True,
    }
