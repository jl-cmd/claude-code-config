#!/usr/bin/env python3
"""
Code style validator - checks for common style issues.

- 4-space indentation (not tabs, not 2 spaces)
- Single newlines between functions (not double)
- Single newlines between class methods
"""
import json
import re
import sys


def check_indentation(content: str) -> list[str]:
    """Check for non-4-space indentation."""
    issues = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        if not line or not line[0].isspace():
            continue

        # Check for tabs
        if '\t' in line:
            issues.append(f"Line {line_num}: Tab indentation - use 4 spaces")
            continue

        # Get leading spaces
        stripped = line.lstrip(' ')
        indent = len(line) - len(stripped)

        # Check if indent is multiple of 4
        if indent > 0 and indent % 4 != 0:
            issues.append(f"Line {line_num}: {indent}-space indent - use 4 spaces")

    return issues[:5]  # Limit to first 5


def check_function_spacing(content: str) -> list[str]:
    """Check for excessive blank lines between code blocks.

    Detects 2+ consecutive blank lines anywhere in the file, plus validates
    correct spacing before function/method/class definitions.
    """
    issues = []
    lines = content.split('\n')

    func_pattern = re.compile(r'^(\s*)(async\s+)?def\s+\w+')
    class_pattern = re.compile(r'^class\s+\w+')

    consecutive_blank_count = 0
    blank_run_start_line = 0
    prev_was_code = False

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            if consecutive_blank_count == 0:
                blank_run_start_line = line_num
            consecutive_blank_count += 1
            continue

        if consecutive_blank_count >= 3:
            issues.append(f"Line {blank_run_start_line}: {consecutive_blank_count} consecutive blank lines - max 2 allowed")

        func_match = func_pattern.match(line)
        class_match = class_pattern.match(line)

        if func_match and prev_was_code:
            indent = len(func_match.group(1)) if func_match.group(1) else 0

            if indent == 0:
                if consecutive_blank_count != 2:
                    issues.append(f"Line {line_num}: Top-level function needs 2 blank lines above (has {consecutive_blank_count})")
            else:
                if consecutive_blank_count != 1:
                    issues.append(f"Line {line_num}: Method needs 1 blank line above (has {consecutive_blank_count})")

        elif class_match and prev_was_code:
            if consecutive_blank_count != 2:
                issues.append(f"Line {line_num}: Class needs 2 blank lines above (has {consecutive_blank_count})")

        consecutive_blank_count = 0
        prev_was_code = not stripped.startswith('#') and not stripped.startswith('@')

    return issues[:5]


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

    # Skip test files (more lenient)
    if 'test' in file_path.lower() or 'conftest' in file_path.lower():
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    content = tool_input.get("content", "") or tool_input.get("new_string", "")

    if not content:
        sys.exit(0)

    if tool_name == "Write":
        try:
            with open(file_path, "r", encoding="utf-8") as existing_file:
                existing_content = existing_file.read()
            if existing_content:
                sys.exit(0)
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            pass

    issues = []
    issues.extend(check_indentation(content))
    issues.extend(check_function_spacing(content))

    if issues:
        issue_list = "; ".join(issues)
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"[Code Style] {len(issues)} issue(s): {issue_list}. Fix or proceed?"
            }
        }
        print(json.dumps(result))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()
