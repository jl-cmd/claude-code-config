# Settings.json Hook Cleanup Guide

Plugin is king. When claude-code-config is installed, it provides complete enforcement.
This guide identifies which ~/.claude/settings.json hook entries are now redundant.

## Principle

The plugin's hooks/hooks.json registers 28 hooks across 8 event types using
`${CLAUDE_PLUGIN_ROOT}`. These run automatically when the plugin is installed.

User settings.json hooks that duplicate plugin hooks will fire TWICE because the
command strings differ (settings.json uses run-hook-wrapper.js, plugin uses python3
directly). Official docs confirm: "Command hooks are deduplicated by command string."
Different strings = no deduplication.

## Classification

### REDUNDANT (plugin provides these -- remove from settings.json)

| Event | Matcher | Hook | settings.json line reference |
|-------|---------|------|------------------------------|
| PreToolUse | Write\|Edit | write-existing-file-blocker.py | blocking/ |
| PreToolUse | Write\|Edit | sensitive-file-protector.py | blocking/ |
| PreToolUse | Write\|Edit | pyautogui-scroll-blocker.py | blocking/ |
| PreToolUse | Write\|Edit | code-rules-enforcer.py | blocking/ |
| PreToolUse | Write\|Edit | tdd-enforcer.py | blocking/ |
| PreToolUse | Write\|Edit | code-style-validator.py | validation/ |
| PreToolUse | Write\|Edit | hook-format-validator.py | validation/ |
| PreToolUse | Edit | refactor-guard.py | advisory/ |
| PreToolUse | Bash | destructive-command-blocker.py | blocking/ |
| PreToolUse | Bash | block-main-commit.py | blocking/ |
| PreToolUse | Bash | pr-description-enforcer.py | blocking/ |
| PreToolUse | Bash | test-preflight-check.py | blocking/ |
| PreToolUse | Task\|Agent | parallel-task-blocker.py | blocking/ |
| PreToolUse | AskUserQuestion | attention-needed-notify.py | notification/ |
| UserPromptSubmit | (all) | bulk-edit-reminder.py | session/ |
| UserPromptSubmit | (all) | code-rules-reminder.py | session/ |
| SessionStart | (all) | plugin-data-dir-cleanup.py | session/ |
| Stop | (all) | attention-needed-notify.py | notification/ |
| Stop | (all) | hedging-language-blocker.py | blocking/ |
| SessionEnd | (all) | session-end-cleanup.py | lifecycle/ |
| ConfigChange | user_settings | config-change-guard.py | lifecycle/ |
| PostToolUse | Write\|Edit | mypy_validator.py | validation/ |
| PostToolUse | Write\|Edit | e2e-test-validator.py | validation/ |
| PostToolUse | Write\|Edit | auto-formatter.py | workflow/ |
| PostToolUse | Agent\|Task\|TeamCreate | investigation-tracker-reset.py | workflow/ |
| Notification | (all) | claude-notification-handler.py | notification/ |

### MUST KEEP (machine-specific or external -- not in plugin)

| Event | Matcher | Hook | Reason |
|-------|---------|------|--------|
| PreToolUse | Read\|Write\|Edit\|Bash\|Glob\|Grep\|Agent\|Task | gate_enforcer.py | Agent-gate (external project at C:/Users/jon/agent-gate/) |
| PreToolUse | Task\|Agent | agent-gate-subagent-bypass-enforcer.py | Agent-gate specific |
| PreToolUse | Task\|Agent | gsd-team-upgrade.py | GSD plugin hook |
| PreToolUse | Glob\|Search\|LS\|etc | gh-wsl-to-windows-redirect.py | Machine-specific WSL/Windows path translation |
| PreToolUse | Grep | content-search-to-zoekt-redirector.py | Machine-specific Zoekt setup |
| PreToolUse | Write\|Edit | gsd-prompt-guard.js | GSD plugin hook |
| UserPromptSubmit | (all) | gate_trigger.py | Agent-gate (external) |
| UserPromptSubmit | (all) | git-account-switcher.py | Machine-specific (3 GitHub accounts) |
| UserPromptSubmit | (all) | apps-script-context.py | Project-specific (Samsung sales) |
| UserPromptSubmit | (all) | tasklings-dev-server-reminder.py | Project-specific (Tasklings) |
| UserPromptSubmit | (all) | voice-profile-injector.py | Machine-specific (personal voice profiles) |
| SessionStart | (all) | session_cleanup.py | Agent-gate (external) |
| SessionStart | (all) | gsd-check-update.js | GSD plugin hook |
| SessionStart | (all) | sync-to-cursor.py | Machine-specific (Cursor IDE sync) |
| SubagentStop | (all) | subagent-complete-notify.py | Optional -- keep if you want desktop notifications for subagents |
| SessionEnd | (all) | cleanup-teammate-session.py | Machine-specific session cleanup |
| PostToolUse | Bash\|Edit\|Write\|etc | gsd-context-monitor.js | GSD plugin hook |
| PostToolUse | Bash | gh-push-failure-detector.py | Machine-specific workflow |

### NOT IN EITHER (hooks in validators/ module)

The plugin's hooks/validators/ module (30+ files) is invoked via run_all_validators.py
which IS registered in hooks.json. Individual validator modules do not need separate
settings.json entries -- they are imported by the runner.

## How to Apply

After confirming the plugin is installed and functional:

1. Open ~/.claude/settings.json
2. In the "hooks" section, remove every entry listed under REDUNDANT above
3. Keep every entry listed under MUST KEEP
4. Restart Claude Code to pick up changes
5. Verify hooks still fire: write a .py file with a magic value (code-rules-enforcer should trigger from the plugin)

## After Cleanup

settings.json hooks section should contain ONLY:
- Agent-gate hooks (gate_enforcer, gate_trigger, session_cleanup, agent-gate-subagent-bypass-enforcer)
- GSD hooks (gsd-*.js, gsd-team-upgrade.py)
- Machine-specific hooks (gh-wsl-to-windows-redirect, content-search-to-zoekt-redirector, sync-to-cursor, voice-profile-injector, git-account-switcher, apps-script-context, tasklings-dev-server-reminder, gh-push-failure-detector, cleanup-teammate-session)
- SubagentStop notification (optional)

Everything else comes from the plugin.
