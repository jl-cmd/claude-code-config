#!/usr/bin/env python3
"""
Block pyautogui mousewheel scroll usage - guide Claude to use pynput instead.

pyautogui's scroll implementation uses incorrect delta values with SendInput API.
pynput uses the same SendInput API but sends correct delta values.
"""
import json
import re
import sys

PYAUTOGUI_SCROLL_PATTERNS = [
    r'pyautogui\.scroll\s*\(',
    r'pyautogui\.hscroll\s*\(',
    r'pyautogui\.vscroll\s*\(',
]

COMPILED_PATTERNS = [re.compile(pattern) for pattern in PYAUTOGUI_SCROLL_PATTERNS]


def check_for_pyautogui_scroll(content: str) -> list[str]:
    """Check for pyautogui scroll function usage."""
    violations = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        for pattern in COMPILED_PATTERNS:
            if pattern.search(line):
                violations.append(f"Line {line_num}: {line.strip()}")
                break

    return violations


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    # Only check Python files
    if not file_path.endswith('.py'):
        sys.exit(0)

    content = tool_input.get("content", "") or tool_input.get("new_string", "")

    if not content:
        sys.exit(0)

    violations = check_for_pyautogui_scroll(content)

    if violations:
        violation_list = "\n".join(f"  • {v}" for v in violations[:5])
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"BLOCKED: pyautogui scroll() is broken on Windows (incorrect delta values). Use pynput instead: from pynput.mouse import Controller; mouse = Controller(); mouse.scroll(0, -3) for scrolling down 3 clicks."
            }
        }
        print(json.dumps(result))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()
