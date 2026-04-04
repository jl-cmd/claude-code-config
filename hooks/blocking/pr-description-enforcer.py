import json
import re
import sys


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    is_pr_create = "gh pr create" in command and ("--body" in command or "-b " in command)
    is_pr_edit = "gh pr edit" in command and "--body" in command
    is_commit = re.search(r'git commit\b', command) and ("-m " in command or "-m\"" in command or "-m'" in command)

    if not (is_pr_create or is_pr_edit or is_commit):
        sys.exit(0)

    body = ""
    if is_pr_create or is_pr_edit:
        body_match = re.search(r'--body\s+"([^"]*)"', command) or re.search(r"--body\s+'([^']*)'", command)
        if body_match:
            body = body_match.group(1)
        heredoc_match = re.search(r'--body\s+"\$\(cat <<', command)
        if heredoc_match:
            body = command[heredoc_match.start():]

    if is_commit:
        msg_match = re.search(r'-m\s+"([^"]*)"', command) or re.search(r"-m\s+'([^']*)'", command)
        if msg_match:
            body = msg_match.group(1)
        heredoc_match = re.search(r'-m\s+"\$\(cat <<', command)
        if heredoc_match:
            body = command[heredoc_match.start():]

    if not body:
        sys.exit(0)

    violations = []

    if is_pr_create or is_pr_edit:
        if "## Summary" not in body and "## summary" not in body.lower():
            violations.append("Missing '## Summary' section")

        has_file_bold = bool(re.search(r'\*\*\w+\.\w+\*\*', body))
        has_bullet_section = bool(re.search(r'###.*(?:test|config|fix)', body, re.IGNORECASE))

        if not has_file_bold and not has_bullet_section:
            violations.append("Production changes must be grouped by file with **filename** bold headers explaining WHY")

        jargon_patterns = [
            (r'\bDexie\b', "Dexie (say 'database' or 'local database')"),
            (r'\bReact Query\b', "React Query (say 'cache' or 'data cache')"),
            (r'\bsyncStatus\b', "syncStatus (describe the behavior, not the field)"),
            (r'\blocalUpdatedAt\b', "localUpdatedAt (describe the behavior, not the field)"),
            (r'\bpullStartedAt\b', "pullStartedAt (describe the behavior, not the field)"),
            (r'\buseMutation\b', "useMutation (describe what it does for the user)"),
        ]
        for pattern, name in jargon_patterns:
            if re.search(pattern, body):
                violations.append(f"Jargon detected: {name}")

    if violations:
        violation_list = "; ".join(violations)
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"BLOCKED: [PR_DESCRIPTION_STYLE] {violation_list}. Use the pr-description-writer custom agent: Agent(subagent_type=\"pr-description-writer\", team_name=\"your-team\", prompt=\"Write PR description for the current branch\").",
            }
        }
        print(json.dumps(result))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()
