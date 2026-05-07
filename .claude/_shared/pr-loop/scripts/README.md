# Shared PR Loop Scripts

| Script | Purpose | Parameters |
|--------|---------|------------|
| `preflight.py` | Pre-flight check: pytest availability, hook install, git tree clean | none |
| `fix_hookspath.py` | Auto-remediate core.hooksPath when preflight fails with hooksPath error | none |
| `code_rules_gate.py` | Run CODE_RULES enforcer against PR diff. Exit 0=pass, 1=advisory, 2=blocking | `--base` (required) |
| `grant_project_claude_permissions.py` | Add project to ~/.claude/settings.json allowlist | none (detects project from CWD) |
| `revoke_project_claude_permissions.py` | Remove project from ~/.claude/settings.json | none |
| `reply_to_inline_comment.py` | Post a reply to a GitHub PR inline comment | `--owner`, `--repo`, `--number`, `--comment-id`, `--body-file` |
