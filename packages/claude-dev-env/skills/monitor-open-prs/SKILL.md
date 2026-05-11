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

## Architecture

The skill spawns one orchestrated team. The orchestrator discovers PRs
and assigns one teammate per PR. Each teammate owns the full bugbot
cycle for its PR from trigger through clean. Teammates spawn
`clean-coder` subagents for fixes but never spawn their own teams.

**Orchestrator (main session):**
1. Discover open PRs via `scripts/discover_open_prs.py`
2. Create team via `TeamCreate`
3. Create one task per PR in the team task list
4. Spawn one `general-purpose` teammate per PR in a single parallel
   `Agent` call
5. Teammates read this skill and execute the bugbot cycle independently
6. Orchestrator waits for all teammates to go idle, collects results,
   emits final report

**Teammate (one per PR):**
1. Reads `state.json` for its PR assignment
2. Runs the full bugbot cycle (trigger → classify → fix → repeat)
3. Spawns `Agent(subagent_type: "clean-coder")` for fixes — never
   `TeamCreate` or `Agent` with `team_name`
4. Writes `state.json` with result before going idle
5. Reports converged / blocked / stuck to orchestrator

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
reports clean on the current HEAD. The cycle per tick:

1. **Resolve PR context** — per-tick.md Step 1. Capture `current_head`,
   owner, repo, branch, number.

2. **Trigger bugbot** — per-tick.md Step 3. Post `bugbot run` via
   `add_issue_comment`. Run bugbot-down detection: capture comment ID,
   wait 15s, check reactions. Zero reactions → `bugbot_down = true`,
   skip to step 6 (terminate). Reactions present → proceed.

3. **Wait for review** — poll
   `pull_request_read(method="get_reviews")` every 60s (up to 10 polls)
   until a review anchored to `current_head` appears with `commit_id ==
   current_head`. Timeout → blocked, report and move to next PR.

4. **Classify** — per-tick.md Step 2 BUGBOT section c, four branches
   (first match wins):
   - No review or `commit_id != current_head` → back to step 2
   - `commit_id == current_head`, zero unaddressed inline, body clean →
     **clean**. This PR is done.
   - `commit_id == current_head` with unaddressed inline → **dirty**.
     Apply fix (step 5), then back to step 2.
   - `commit_id == current_head`, body findings, inline API zero
     matching → **inline_lag**. Increment `inline_lag_streak`. >= 3 →
     hard blocker, report and move to next PR. Else wait 90s, retry
     step 4.

5. **Fix** — per
   [fix-protocol.md](~/skills/pr-converge/reference/fix-protocol.md)
   Single-PR fix workflow, executed via `Agent` subagent. The agent
   prompt follows the structured prompt pattern from
   [pr-converge fix dispatch](https://github.com/jl-cmd/claude-code-config/pull/422):
   - Read each referenced file:line
   - Write failing test first when finding has behavior to test
   - Implement via `Agent` (`subagent_type: "clean-coder"`).
     Full-stop if unavailable.
   - Stage, commit, push (honor pre-commit and pre-push hooks;
     full-stop on bypass)
   - Reply inline on each addressed thread via
     `add_reply_to_pull_request_comment`
   - Set `current_head` to new SHA
   - Back to step 2

6. **Bugbot-down** — when `bugbot_down == true`, terminate immediately.
   Bugbot is unreachable; further cycles would busy-loop. Report the PR
   as blocked with reason `bugbot_down`.


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
