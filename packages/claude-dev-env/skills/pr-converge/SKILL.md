---
name: pr-converge
description: >-
  Drives the current PR to convergence by looping Cursor Bugbot, a
  second-opinion bug audit, and Copilot — applying TDD fixes, posting
  inline replies, and re-triggering reviewers each tick until all three
  reviewers are clean on the same HEAD. Use when the user says
  '/pr-converge', 'drive PR to convergence', 'loop bugbot and bugteam',
  'babysit bugbot and bugteam', 'until both are clean', or 'converge this
  PR'.
---

# PR Converge

One tick per invocation. Bugbot ↔ bugteam ↔ Copilot loop on a draft PR
until all three are clean on the same `HEAD` and mergeable.

## Pre-flight

`ScheduleWakeup` not in this turn's tool registry → abort. Report
`pr-converge requires ScheduleWakeup; aborting` and return.

## Gotchas

Highest-signal content. Append a bullet each time a tick fails in a new
way — these are the hard-won lessons that keep the loop honest. Once this
grows to 5 or more items, suggest spinning up a subagent to investigate, fix,
post a fresh PR in a fresh branch based on origin main to the user.

- **`ScheduleWakeup` not in subagent tool registries** — background
  `general-purpose` tick cannot schedule re-entry; only parent session
  with `ScheduleWakeup` in registry can call it.
- **Review body and inline comments desync for same `commit_id`** —
  "dirty body, zero inline rows at `current_head`" is **`inline_lag`**,
  not **`dirty`**. Bump `inline_lag_streak`, wait 90s, retry fetch.
- **`state.json` without §Concurrency lock loses merges** when teammates
  finish in same wall-clock window.
- **`tick_count` must not double-increment** — conversation state line
  only when **no** `state.json`; with `state.json`, only the
  orchestrator bump increments.
- **Duplicate `bugbot run` while review queued** — skip Step 3 when the
  latest `bugbot run` PR comment has an `:eyes:` or `:+1:` reaction;
  wait for review or HEAD change before re-triggering.
- **Bugbot unresponsive after `bugbot run` post** — after posting the
  trigger comment via `add_issue_comment`, capture the returned comment
  ID. Wait 15s, then check for reactions on that specific comment via
  `issue_read(method="get_comments", owner=OWNER, repo=REPO, issue_number=NUMBER)`
  matching on the captured ID. Zero reactions means bugbot is down; set
  `bugbot_down = true`, `phase = BUGTEAM`, and jump to Step 2 BUGTEAM
  branch in this same tick so bugteam runs immediately against this
  HEAD without a wakeup cycle. **Reactions present (`:eyes:` or `:+1:`)
  → record `bugbot_acknowledged_at = <now ISO 8601>` on the trigger
  comment id and proceed with normal pacing. Subsequent BUGBOT ticks
  honor a 30-minute wall-clock budget after `bugbot_acknowledged_at`:
  while the latest cursor[bot] review's `commit_id` ≠ `current_head`
  AND the budget is unspent, schedule the next 270s wakeup. Once
  `now - bugbot_acknowledged_at > 30 min` with no review surfaced at
  `current_head`, treat as bugbot effectively down — set
  `bugbot_down = true`, `phase = BUGTEAM`, jump to Step 2 BUGTEAM same
  tick.** The 30-minute budget is the empirical worst-case turnaround
  seen on 80+ KB diffs; 2-4 minutes is typical, but bursts back up to
  ~30 minutes on Cursor-side queue saturation.
- **Bot login fields differ by endpoint** — `get_reviews` returns
  `.user.login` (object), but `get_review_comments` returns `.author`
  (string, not an object). Threads use `is_outdated` (not `commit_id`) to
  indicate staleness. Always check the correct fields and use
  case-insensitive substring matching on login values, never strict
  equality.
- **MCP `pull_request_read(method="get_reviews"|"get_review_comments")`
  silently truncates large lists** — the GitHub MCP server caps each
  response at ~28-30 entries regardless of the `page` and `perPage`
  parameters. On PRs with heavy review activity (one bugteam audit
  loop alone posts 26 inline review-replies, all tagged with the same
  HEAD SHA), the latest cursor[bot] / Copilot review for `current_head`
  lands past the cutoff and the MCP-only walk reports "no review yet"
  for tens of minutes after the review actually exists. `inline_lag` is
  the wrong diagnosis; **the data is in GitHub, the MCP just refuses to
  return it**. Bypass the MCP for any review/comment fetch on a PR with
  more than ~25 reviews or comments. The canonical bypass uses `gh api
  --paginate --slurp | jq` from the `Bash` tool (this rule lives in
  `~/.claude/rules/gh-paginate.md`):

  ```bash
  # Latest cursor[bot] review across the whole PR (newest first)
  gh api 'repos/<owner>/<repo>/pulls/<N>/reviews?per_page=100' --paginate --slurp \
    | jq '[.[][] | select((.user.login | ascii_downcase) | contains("cursor"))]
           | sort_by(.submitted_at) | reverse | .[0]'

  # Newest cursor[bot] review pinned to a specific HEAD SHA
  gh api 'repos/<owner>/<repo>/pulls/<N>/reviews?per_page=100' --paginate --slurp \
    | jq --arg sha '<current_head>' \
        '[.[][] | select((.user.login | ascii_downcase) | contains("cursor"))
                | select(.commit_id == $sha)]
         | sort_by(.submitted_at) | reverse | .[0]'

  # Unaddressed cursor[bot] inline threads on the latest HEAD
  gh api 'repos/<owner>/<repo>/pulls/<N>/comments?per_page=100' --paginate --slurp \
    | jq '[.[][] | select((.user.login | ascii_downcase) | contains("cursor"))]
           | sort_by(.created_at) | reverse'

  # Newest Copilot review at HEAD
  gh api 'repos/<owner>/<repo>/pulls/<N>/reviews?per_page=100' --paginate --slurp \
    | jq --arg sha '<current_head>' \
        '[.[][] | select((.user.login | ascii_downcase) | contains("copilot"))
                | select(.commit_id == $sha)]
         | sort_by(.submitted_at) | reverse | .[0]'

  # All issue comments on the PR (for bugbot-trigger reaction lookup)
  gh api 'repos/<owner>/<repo>/issues/<N>/comments?per_page=100' --paginate --slurp \
    | jq '[.[][]] | sort_by(.created_at) | reverse'
  ```

  `--paginate --slurp` walks every page AND emits a single merged
  `[[page1...], [page2...], ...]` array — the `.[][]` flatten is what
  makes cross-page `sort_by(.submitted_at) | reverse | .[0]` correct.
  `--paginate --jq` is forbidden here because `gh`'s `--jq` runs
  per-page, so the cross-page sort silently returns the wrong entry.
  Only the BUGBOT / COPILOT_WAIT review-existence and inline-comment
  fetches need this bypass; single-object MCP reads (`pull_request_read`
  with `method="get"`, `add_issue_comment`,
  `add_reply_to_pull_request_comment`,
  `pull_request_review_write`) stay on the MCP — they return one record
  with no pagination involved.
- **PR branch checked out in a different worktree** —
  `git branch --show-current != .head.ref` → run `per-tick.md` Step 0.

## First tick of a session

Read [`reference/state-schema.md`](reference/state-schema.md),
[`reference/ground-rules.md`](reference/ground-rules.md), then
[`reference/per-tick.md`](reference/per-tick.md).

## Match situation, read spoke

| Situation | Read |
|---|---|
| Starting any tick | [`reference/per-tick.md`](reference/per-tick.md) |
| Bugbot or audit finding to fix and push | [`reference/fix-protocol.md`](reference/fix-protocol.md) |
| Bugteam reports `convergence (zero findings)` AND `bugbot_clean_at == current_head` | [`reference/convergence-gates.md`](reference/convergence-gates.md) |
| Multi-PR session — `state.json` exists at `<TMPDIR>/pr-converge-<session_id>/` | [`reference/multi-pr-orchestration.md`](reference/multi-pr-orchestration.md) |
| Scheduling the next wakeup | [`workflows/schedule-wakeup-loop.md`](workflows/schedule-wakeup-loop.md) |
| Hard blocker, convergence reached, or user stops loop | [`reference/stop-conditions.md`](reference/stop-conditions.md) |
| All GitHub interactions use `plugin:github:github` MCP tools | [`reference/per-tick.md`](reference/per-tick.md) |
| Tick is ambiguous against the spokes above | [`reference/examples.md`](reference/examples.md) |

## Folder map

- `SKILL.md` — this hub.
- `reference/` — workflow detail per situation.
- `workflows/` — pacing implementations.
