# Gate-Audit Install Runbook

Operational runbook for the global git-hooks install + SessionStart self-healer that backs the gate-leak audit.

## State as of this writing

- `core.hooksPath` (global): `C:\Users\jon\.claude\hooks\git-hooks`
- Shims present: `pre-commit`, `pre-push`, `post-commit` (with paired `*.py` modules)
- SessionStart self-healer: registered in `packages/claude-dev-env/hooks/hooks.json`, source at `packages/claude-dev-env/hooks/session/git_hooks_self_heal.py`
- Effect: every git repo on the machine inherits gate enforcement via the user-global `core.hooksPath`. New clones and `git init`s pick it up automatically.

## What each layer enforces

| Layer | Fires on | Scope | What it blocks |
|---|---|---|---|
| PreToolUse `Write\|Edit` | Claude tool write | full new file content | All CODE_RULES violations on writes from Claude |
| pre-commit | `git commit` | `git diff --cached` added lines | New violations on staged additions |
| pre-push | `git push` | `git diff <merge-base>..HEAD` added lines | New violations in unpushed commits |
| post-commit | after `git commit` | submodule linkage | Submodule sync only — no rule blocking |

The git layers run the same `code_rules_enforcer.validate_content()` as PreToolUse but scope checks to **added lines only** (per `split_violations_by_scope`). Pre-existing violating code is intentionally not blocked at commit time.

## Verify install is intact

```pwsh
git config --global --get core.hooksPath
# → C:\Users\jon\.claude\hooks\git-hooks (or equivalent)

Test-Path ~/.claude/hooks/git-hooks/pre-commit
Test-Path ~/.claude/hooks/git-hooks/pre-push
Test-Path ~/.claude/hooks/git-hooks/post-commit
# all → True
```

## Verify the gate fires end-to-end

From a temp repo with a deliberate violation:

```pwsh
$repo = Join-Path $env:TEMP "gate-smoke-$(Get-Random)"
git init $repo
"MAGIC = 42`n" | Set-Content (Join-Path $repo "scratch.py")
git -C $repo add scratch.py
git -C $repo commit -m "smoke"
# Expect block with: BLOCKED: [CODE_RULES] N violation(s): ...
Remove-Item -Recurse -Force $repo
```

## Recover the install (manual)

If `core.hooksPath` is unset or the shim files vanish, re-run the installer once:

```pwsh
node packages/claude-dev-env/bin/git_hooks_installer.mjs
```

The SessionStart self-healer (`hooks/session/git_hooks_self_heal.py`) does this automatically on every Claude Code launch — you only need this command if you're recovering outside a Claude session.

## Recover the install (automatic)

The SessionStart self-healer runs on every Claude Code session start. It:
1. Reads `core.hooksPath`.
2. If unset → invokes the installer. If set to the expected directory but a shim file is missing → invokes the installer. If set to anything else (husky, lefthook, custom) → exits silently.
3. On installer failure, prints one stderr line and exits 0 — never blocks the session.

Source: `packages/claude-dev-env/hooks/session/git_hooks_self_heal.py`. Tests: `test_git_hooks_self_heal.py` (8 cases, all green).

## Per-repo opt-out

```pwsh
git -C <repo> config core.hooksPath .git/hooks
# Local override; SessionStart self-healer respects it (only re-installs when global is unset or pointing at the expected target).
```

## Full rollback

```pwsh
git config --global --unset core.hooksPath
# Reverts every repo to its own .git/hooks/. Shim files under ~/.claude/hooks/git-hooks/ become inert.
# Disable the SessionStart self-healer too, or it will reinstall on next session:
# remove the entry pointing at git_hooks_self_heal.py from packages/claude-dev-env/hooks/hooks.json
```

## Re-running the audit

```pwsh
python run_gate_audit.py
# Compares against the same scope (last 20 squash-merges per discoverable repo).
# Outputs gate_audit_report.json and .md in this worktree root.
```

After Phase 3 fix-PRs land, expected: total leak count drops sharply (especially `naming_collections` and `magic_values`). Residual leaks would surface either rule-engine gaps or violations on lines outside the diff window of the historical sample.

## Where to look when something breaks

| Symptom | First file to check |
|---|---|
| Hook doesn't fire on commit | `git config --global --get core.hooksPath` (must resolve to `~/.claude/hooks/git-hooks`) |
| Shim missing | `~/.claude/hooks/git-hooks/{pre-commit,pre-push,post-commit}` |
| Self-healer error in session start | stderr in last session; source `packages/claude-dev-env/hooks/session/git_hooks_self_heal.py` |
| Gate script can't find `bugteam_code_rules_gate.py` | `~/.claude/skills/bugteam/scripts/bugteam_code_rules_gate.py` (path from `git-hooks/config.py`) |
| Audit JSON shows wrong rule labels | `run_gate_audit.py` keyword→rule mapping table |
