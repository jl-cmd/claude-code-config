# Gate Audit Report

**Date:** 2026-05-01  **Runtime:** 195s  **Partial:** False

**Repos discovered:** 19  **Repos audited:** 19  **PRs audited:** 80

**Total findings:** 353  **Hook-infra exclusions:** 27

## Top 5 Leaking Rules

| Rule | Count |
|------|-------|
| naming_collections | 123 |
| magic_values | 62 |
| code_rules_other | 61 |
| naming_loop_variables | 19 |
| imports_at_top | 15 |

## Top 3 Repos by Leak Count

| Repo | Count |
|------|-------|
| jl-cmd/prompt-generator | 123 |
| JonEcho/theme-asset-db | 105 |
| jl-cmd/claude-code-config | 49 |

## Layer Coverage

The audit covered only the PreToolUse `Write|Edit` enforcer. There are four enforcement layers in this codebase; their actual install state and scope:

| Layer | Trigger | Scope | Source path | Install state |
|---|---|---|---|---|
| PreToolUse `Write\|Edit` | Claude tool write | full new file content | `packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py` | active (user-global) |
| pre-commit | `git commit` | `git diff --cached` **added lines only** | `packages/claude-dev-env/hooks/git-hooks/pre_commit.py` | **installed globally** via `core.hooksPath` |
| pre-push | `git push` | `git diff <merge-base>..HEAD` **added lines only** | `packages/claude-dev-env/hooks/git-hooks/pre_push.py` | **installed globally** via `core.hooksPath` |
| post-commit | `git commit` (after) | submodule linkage only — no rule enforcement | `packages/claude-dev-env/hooks/git-hooks/post_commit.py` | installed globally |

`core.hooksPath` is set globally to `~/.claude/hooks/git-hooks/`, so every repo on the machine inherits the git layers — including the 19 audited. The audit's `git_hooks_present: []` was a probe defect (it checked `<repo>/.git/hooks/` instead of resolving `core.hooksPath`).

**The 353 leaks are NOT from missing install.** They come from two structural gaps:

1. **Pre-commit is added-line-scoped.** `split_violations_by_scope` in the gate script blocks only violations on lines the diff added; pre-existing violating code passes through. The audit ran the enforcer against full file content, so it surfaces violations the pre-commit hook intentionally lets through.
2. **PreToolUse only fires on Claude `Write|Edit`.** Manual IDE edits, post-Claude refactors, and any commit made outside Claude bypass the gate entirely.

## Hook Installation Summary

| Effective Install | Repos |
|---|---|
| yes (local or plugin) | 2 |
| user_global_only | 17 |
| no | 0 |

All 19 audited repos have PreToolUse hooks via `~/.claude/settings.json` and git hooks via global `core.hooksPath`.

## Recommendations

1. **Fix the 353 historical violations.** Concentrated: 78% in 3 repos (jl-cmd/prompt-generator 123, JonEcho/theme-asset-db 105, jl-cmd/claude-code-config 49); 60% in 10 files. Most fixes are mechanical renames (`environment_overrides` → `all_environment_overrides`) or `config/` extractions. Per-repo PRs run by `/agent-prompt`-dispatched fix agents. Tracked in this plan as Phase 3.
2. **Triage the 61 `code_rules_other`.** Pre-research clustered them: 36 are `constants_location` mapping misses, 11 `no_abbreviations`, 8 `unjustified_type_ignore`, etc. — all map to existing enforcer rules. Fix is a `run_gate_audit.py` mapping-table extension. Tracked as Phase 2.
3. **Investigate enforcer scope around `config.py` files outside `/config/`.** `scripts/midjourney_ingest/config.py` flagged 18 `magic_values`. The enforcer's `is_config_file()` may only exempt paths containing `/config/`, not files named `config.py`. Verify before fixing.
4. **Verify enforcer naming-rule reach.** 123 `naming_collections` leaks suggest the rule fires correctly but is being added in places PreToolUse missed (manual edits, refactors). Phase 3 fixes the existing leaks; future leaks are blocked by the now-active git hooks.

## Hook Infrastructure Exclusion Note

The enforcer's `is_hook_infrastructure()` guard automatically skips files under `/.claude/hooks/` and `packages/claude-dev-env/hooks/`. This audit recorded **27** such exclusions (primarily from jl-cmd/claude-code-config). These are correct behavior, not missed checks.

## Deferred Rules

The following rules require diff-semantic judgment and cannot be pattern-matched:
- `solid_srp`
- `self_contained_components`
- `comments_as_feedback`

## Skipped Repos

_No repos skipped._

## Anomalies

- **jl-cmd/florida-blue-claim-filler**: no squash-merge commits found in last 50 commits
- **JonEcho/focus-zones-native**: no squash-merge commits found in last 50 commits
- **jl-cmd/agent-gate**: no squash-merge commits found in last 50 commits
- **JonEcho/babysit-pr**: no squash-merge commits found in last 50 commits
- **jl-cmd/claude-workflow**: no squash-merge commits found in last 50 commits
- **jl-cmd/groq-prompt-scorer**: no squash-merge commits found in last 50 commits
- **jl-cmd/reddit-post-optimizer**: no squash-merge commits found in last 50 commits
- **jl-cmd/skill-sync**: no squash-merge commits found in last 50 commits
- **JonEcho/theme-skills**: no squash-merge commits found in last 50 commits
- **jl-cmd/einstein-skills**: no squash-merge commits found in last 50 commits
- **jl-cmd/one-great-ride-website**: no squash-merge commits found in last 50 commits
- **jl-cmd/snake-game**: no squash-merge commits found in last 50 commits
- **jl-cmd/YNAB-Automation**: no squash-merge commits found in last 50 commits