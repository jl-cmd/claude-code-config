#!/usr/bin/env python3
import json
import os
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CODE_RULES_PATH = os.path.join(PLUGIN_ROOT, "docs", "CODE_RULES.md")


def load_code_rules() -> str:
    try:
        with open(CODE_RULES_PATH, encoding="utf-8") as code_rules_file:
            return code_rules_file.read()
    except (FileNotFoundError, OSError):
        return ""


def main() -> None:
    try:
        json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    code_rules_content = load_code_rules()
    if not code_rules_content:
        sys.exit(0)

    reinject_payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": code_rules_content,
        }
    }
    print(json.dumps(reinject_payload))
    sys.exit(0)


if __name__ == "__main__":
    main()
