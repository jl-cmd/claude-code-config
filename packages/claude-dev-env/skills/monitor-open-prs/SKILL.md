---
name: monitor-open-prs
description: >-
  Discover every open pull request across configured owner scopes, run a
  bugbot-only fix loop on each (trigger → classify → fix via clean-coder →
  repeat until clean), and poll for late bugbot findings after convergence.
  Triggers: '/monitor-open-prs', 'sweep the open PRs', 'audit the open PR
  backlog'.
---

# Monitor Open PRs

Bugbot-only sweep over every open PR across configured owner scopes.
Discover live via `scripts/discover_open_prs.py`, run the bugbot cycle
per PR, poll for late findings, report.

## Contents

- Architecture — orchestrated team: one orchestrator, one teammate per PR
- When this skill applies — refusal cases and trigger conditions
- Configuration — git-ignored owner scope config file
- Discovery — `scripts/discover_open_prs.py` queries `gh search prs` across configured owner scopes
- Bugbot cycle — trigger, classify, fix, repeat per PR (delegated to teammates)
- Post-convergence polling — backoff poll for late bugbot findings
- Final report

## Gotchas

- **Teammates cannot spawn teams.** `Agent` with `team_name` or `TeamCreate`
  from within a teammate silently fails. Teammates spawn only
  `Agent(subagent_type: "clean-coder", run_in_background=true)` for fixes.
- **`bugbot run` duplicate while review queued.** Skip trigger when the
  latest `bugbot run` PR comment has an `:eyes:` or `:+1:` reaction. Wait
  for review or HEAD change first.
- **Review body and inline comments desync.** "Dirty body, zero inline at
  `current_head`" is `inline_lag`, not `dirty`. Bump streak, wait 90s,
  retry. Do not spawn clean-coder for lag.
- **Bot login fields differ by endpoint.** `get_reviews` returns
  `.user.login` (object); `get_review_comments` returns `.author`
  (string). Use case-insensitive substring matching, never strict equality.
- **`state.json` lost-update on parallel writes.** Naive read-modify-write
  loses merges when teammates finish in the same window. Use the
  atomic lock + replace protocol from
  pr-converge's multi-pr-orchestration.md §Concurrency.

## Architecture

The skill spawns one orchestrated team. The orchestrator discovers PRs
and assigns one teammate per PR. Each teammate owns the full bugbot
cycle for its PR from trigger through clean. Teammates spawn
`clean-coder` subagents for fixes but never spawn their own teams.

**Dependencies:** pr-converge skill (for per-tick.md and fix-protocol.md
spokes), clean-coder agent (for fix implementation), GitHub MCP server.

**Orchestrator workflow:**

Use `TaskCreate` to build a task list the orchestrator works through.
Mark each complete with `TaskUpdate` when done.

1. `TaskCreate(subject: "Discover open PRs")` — Run
   `scripts/discover_open_prs.py`. Mark complete.
2. `TaskCreate(subject: "Create orchestration team")` — Call
   `TeamCreate`. Mark complete.
3. For each discovered PR, `TaskCreate(subject: "<owner>/<repo>#<number>")`
   with description holding owner/repo/number/branch. These are the
   per-PR work items assigned to teammates.
4. Spawn one `Agent` teammate per PR in a single parallel call. Each
   teammate reads this skill and claims its assigned task.
5. Wait for all teammates to go idle.
6. `TaskCreate(subject: "Emit final report")` — Collect teammate
   results, emit the report from the Final report section. Mark complete.

**Teammate checklist (bugbot-sweep-agent):**

```
[ ] Read this skill and follow the Bugbot cycle section below
[ ] Run the cycle until clean, blocked, or stuck
[ ] Spawn Agent(subagent_type: "clean-coder") for fixes — never TeamCreate
[ ] Write state.json with result before going idle
[ ] Report converged / blocked / stuck to orchestrator
```

## When this skill applies

`/monitor-open-prs` authorizes one full sweep over all open PRs in the
configured owner scopes.

Refusals — first match wins; respond with the quoted line exactly and stop:

- **GitHub MCP not accessible.** `get_me failed. /monitor-open-prs needs active GitHub MCP credentials.`
- **`clean-coder` subagent not available.** Fetch from
  `jl-cmd/claude-code-config` public repo. If still unavailable:
  `Required subagent type clean-coder not installed.`

## Configuration

Owner scopes are read from a git-ignored config file at
`scripts/config/owners.json` in the skill directory. Format:

```json
{
  "owners": ["jl-cmd", "JonEcho"]
}
```

If the file is absent, the skill prompts for the owner list on first run
and writes the config. The `scripts/` directory ships a `.gitignore`
entry for `config/` so owner lists are never committed.

## Discovery

Call `scripts/discover_open_prs.discover_open_prs(all_owners=<owners from config>)`
to retrieve the live open-PR list across all configured owner scopes.
The helper shells out to `gh search prs --owner <owner> --state open
--json number,repository,url,headRefName,baseRefName` for each owner
scope and flattens the result to a uniform dict shape with keys
`number`, `owner`, `repo`, `head_ref`, `base_ref`, `url`. Empty scopes
contribute empty lists; an entirely empty sweep returns `[]` and exits
cleanly.

## Bugbot cycle

For each discovered PR, run the BUGBOT phase from
[pr-converge](~/skills/pr-converge/reference/per-tick.md) until bugbot
reports clean on the current HEAD. Copy this checklist into your response
and check off each step as you go.

```
[ ] 1. Resolve PR context — per-tick.md Step 1
       Capture current_head, owner, repo, branch, number.
[ ] 2. Trigger bugbot — per-tick.md Step 3
       Post "bugbot run" via add_issue_comment. Run bugbot-down
       detection: capture comment ID, wait 15s, check reactions.
       Zero reactions → bugbot_down = true → skip to step 6.
       Reactions present → proceed.
[ ] 3. Wait for review
       Poll pull_request_read(method="get_reviews") every 60s (max 10)
       until a review at current_head appears. Timeout → blocked.
[ ] 4. Classify — per-tick.md Step 2 BUGBOT §c, first match wins:
       - No review or commit_id != current_head → back to step 2
       - Clean (body clean, zero unaddressed inline) → DONE
       - Dirty (unaddressed inline at current_head) → step 5
       - inline_lag (body dirty, inline API zero) → bump streak,
         wait 90s, retry step 4 (>= 3 → hard blocker)
[ ] 5. Fix — delegating to clean-coder per fix-protocol.md Single-PR
       Spawn Agent(subagent_type: "clean-coder", run_in_background=true)
       listing the dirty file:line findings. After clean-coder returns,
       set current_head to new SHA, go to step 2.
[ ] 6. Bugbot-down — terminate immediately, report blocked/bugbot_down
```


## Post-convergence polling

After a PR's bugbot cycle returns clean, poll for late findings:

1. Baseline: capture `since_timestamp` as the PR's last commit timestamp.
2. Every 120s, call `pull_request_read(method="get",
   pullNumber=<pr_number>, owner=<owner>, repo=<repo>)` and filter
   comments for bugbot/cursor entries with `.createdAt` after
   `<since_timestamp>`.
3. Back off: 120s → 240s → 480s → 960s → 15000s. Five successive empty
   polls → exit polling for this PR.
4. If bugbot posts a new finding, re-enter the bugbot cycle at step 2.

## Final report

```
/monitor-open-prs sweep summary
PRs discovered: <N>
  <owner>/*: <count>  (one line per configured owner)
PRs clean: <count>
PRs blocked (inline_lag >= 3): <count>
PRs blocked (bugbot_down): <count>
PRs errored: <count>
PRs stuck (review timeout): <count>
Bugbot re-triggers fired: <count>
```

## Non-negotiable guardrails

- Never pass `--no-verify` or `--no-gpg-sign` to git.
- Never open a PR from this skill; only comment on existing ones.
- Never merge or close PRs; read + audit + patch only.

## Folder map

- `SKILL.md` — this hub
- `scripts/discover_open_prs.py` — `gh search prs` discovery helper
- `scripts/config/owners.json` — git-ignored owner scope configuration
- `scripts/test_discover_open_prs.py` — tests for the discovery helper
- `test_skill_contract.py` — skill-level contract tests
