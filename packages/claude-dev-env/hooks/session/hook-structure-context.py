#!/usr/bin/env python3
"""
UserPromptSubmit hook that detects "hook" mentions and injects
context about our current hook structure and how to add new hooks.
"""

import json
import sys


TRIGGER_PHRASES = [
    "hook",
]

EXCLUDE_PHRASES = [
    "react hook",
    "usehook",
    "usestate",
    "useeffect",
    "custom hook",
    "git hook",
    "pre-commit hook",
    "webhook",
]

CONTEXT = """
<hook-structure-context>
## Claude Code Hook System

### Architecture
- **Runner pattern**: `run-hook-wrapper.js` (Node.js) -> `run-hook.py` (Python) -> individual hook
- **Hook directory**: `hooks/`

### Hook Organization (subfolder structure)
```
hooks/
|-- rewrite-plugin-paths.py
|-- session/
|   |-- compact-context-reinject.py
|   |-- plugin-data-dir-cleanup.py
|   +-- hook-structure-context.py
|-- notification/
|   |-- attention-needed-notify.py
|   |-- claude-notification-handler.py
|   +-- notification_utils.py
|-- advisory/
|   |-- refactor-guard.py
|   +-- migration-safety-advisor.py
|-- validation/
|   |-- code-style-validator.py
|   |-- hook-format-validator.py
|   |-- mypy_validator.py
|   +-- e2e-test-validator.py
|-- lifecycle/
|   |-- config-change-guard.py
|   +-- session-end-cleanup.py
|-- blocking/
|   |-- pyautogui-scroll-blocker.py
|   |-- sensitive-file-protector.py
|   |-- write-existing-file-blocker.py
|   +-- destructive-command-blocker.py
|-- git-hooks/
|   +-- post-commit.py
|-- github-action/
|   +-- test_workflow.py
+-- validators/
    |-- (validation check modules)
    +-- test_files/
```

### Event Types
| Event | When | Input (stdin JSON) | Can Block? |
|-------|------|-------------------|------------|
| SessionStart | Session begins | `{}` | No |
| UserPromptSubmit | User sends message | `{"prompt": "..."}` | No (advisory) |
| PreToolUse | Before tool execution | `{"tool_name": "...", "tool_input": {...}}` | YES (exit 2) |
| PostToolUse | After tool execution | `{"tool_name": "...", "tool_input": {...}, "tool_output": "..."}` | No |
| SubagentStop | Agent completes | `{"agent_type": "...", ...}` | No |
| Stop | Session ends | `{}` | No |

### How to Add a New Hook

1. **Create the hook file** in the appropriate subfolder:
   ```python
   #!/usr/bin/env python3
   import json
   import sys

   hook_input = json.load(sys.stdin)
   print("Context to inject")
   sys.exit(0)
   ```

2. **Register in settings.json** under the correct event type:
   ```json
   {
     "type": "command",
     "command": "node -e \\"process.argv.splice(1,0,'_');require(require('os').homedir()+'/.claude/hooks/run-hook-wrapper.js')\\" \\"session/your-hook.py\\"",
     "timeout": 15000
   }
   ```

3. **Key rules**:
   - Always use the `run-hook-wrapper.js` pattern (cross-platform)
   - Set explicit timeouts (10000-30000ms)
   - PreToolUse hooks use `matcher` to scope which tools they fire on
   - UserPromptSubmit hooks match on `prompt` content
   - Print output = context injected into Claude's conversation
   - Advisory hooks exit 0; blocking hooks exit 2 with `hookSpecificOutput.permissionDecision`
</hook-structure-context>
"""


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    prompt = hook_input.get("prompt", "")

    if not prompt:
        sys.exit(0)

    message_lower = prompt.lower()

    for exclude in EXCLUDE_PHRASES:
        if exclude in message_lower:
            sys.exit(0)

    for phrase in TRIGGER_PHRASES:
        if phrase in message_lower:
            print(CONTEXT)
            sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
