# Team Setup

## Composition

| Role | Subagent Type | Model | Count |
|------|--------------|-------|-------|
| Auditor | `eval-code-quality-agent` | opus | 1 per loop |
| Fixer | `eval-clean-coder` | opus | 1 per loop |

## Subagent Lifecycle

1. **Spawn** at AUDIT or FIX action via `Agent(run_in_background=true)`
2. **Execute** in the PR's worktree (`<run_temp_dir>/pr-<N>/worktree`)
3. **Return** outcome XML path on stdout
4. **Lead consumes** XML output synchronously

## Grant/Revoke

At session start (Step 0), the project's `.claude/**` directory is granted
permissions via `grant_project_claude_permissions.py`. At session end
(Step 5), permissions are revoked via `revoke_project_claude_permissions.py`.
This enables subagents to read skill files and scripts.
