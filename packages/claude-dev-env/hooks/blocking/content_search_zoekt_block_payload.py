def build_block_payload(brief_label: str, full_reason: str) -> dict:
    destructive_gate_label_prefix = "[destructive-gate]"
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
        },
        "decision": "block",
        "reason": full_reason,
        "systemMessage": f"{destructive_gate_label_prefix} {brief_label}",
        "suppressOutput": True,
    }
