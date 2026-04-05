#!/usr/bin/env python3
import json
import sys

BULK_UPDATE_KEYWORDS = ["update all", "replace all", "change all", "fix all", "rename all"]

BULK_UPDATE_REMINDER = "BULK UPDATE DETECTED: Use a Python script with --preview/--apply instead of line-by-line edits."


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    prompt = input_data.get("prompt", "")

    if not prompt:
        sys.exit(0)

    message_lower = prompt.lower()

    if any(keyword in message_lower for keyword in BULK_UPDATE_KEYWORDS):
        print(BULK_UPDATE_REMINDER)

    sys.exit(0)


if __name__ == "__main__":
    main()
