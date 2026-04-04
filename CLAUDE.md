# Development Environment

## Plugin Ecosystem

claude-code-config is the primary plugin providing rules, docs, agents, commands, skills, and hooks. All behavioral rules live in `.claude/rules/` files. Additional plugins: claude-journal, claude-deep-research, claude-workflow, GSD (npx get-shit-done-cc).

## Agent Gate

The `agent-gate` MCP server evaluates prompts before execution. The `gate_enforcer.py` PreToolUse hook blocks execution tools until `evaluate_prompt` clears. Subagents bypass the gate via a `*` prefix in their prompt.

## Obsidian Vault

Search with `mcp__obsidian__search_notes` before starting substantive work. Prior sessions and decisions inform current tasks.

- `sessions/[Project]/` -- session reports
- `decisions/` -- active or superseded decisions
- `Research/` -- deep research documents

## Search Tools

- zoekt MCP server for indexed code search
- Context7 MCP for current library and framework docs
- Everything `es.exe` for fast file search (Windows environments)

## Git

Multiple GitHub accounts configured via SSH. The `git-account-switcher.py` hook auto-detects the correct account per repo.

## Hooks

Settings.json hooks are machine-specific only. Plugin hooks are registered via the plugin system. The two do not overlap.

## Gotchas

- Python command varies by platform. Detect which of `python3`, `python`, or `py -3` resolves to Python 3.12+.
- Network drives can be slow for git. Clone to local temp dirs for intensive operations.
- The agent-gate MCP server disconnects intermittently. Run `/mcp` to reconnect if tools are blocked but the MCP tool is unavailable.
- On Windows, Python hooks route through a `node` wrapper (`run-hook-wrapper.js`) for stdin piping.
