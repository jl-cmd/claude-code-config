# Unified queue: jl-cmd + pinned JonEcho

This workflow mirrors the **unified work queue** used when converging **multiple repositories** in one session: all **open** pull requests on `jl-cmd/claude-code-config`, plus each **open or draft** pull request listed under [Pinned PR queue (JonEcho)](#pinned-pr-queue-jonecho). It is the installable counterpart to any Cursor-local `parallel-debug` skill wrapper; **per-tick** bugbot ↔ bugteam behavior, Fix protocol, and stop rules live in the parent [`SKILL.md`](../SKILL.md).

**Pacing:** When `ScheduleWakeup` is unavailable, start and stop the AHK auto-continue driver per [`ahk-auto-continue-loop.md`](ahk-auto-continue-loop.md). Do **not** call `ScheduleWakeup` from a session that uses AHK pacing.

Use **`${CLAUDE_SKILL_DIR}`** in commands below so paths resolve to the installed skill folder (for example `$HOME/.claude/skills/pr-converge/`).

## Objective

Converge every **active** item in the unified queue to **back-to-back clean**: Bugbot **CLEAN** and second audit (**bugteam**) **CLEAN** at the same `HEAD`. The queue is:

1. All **open** pull requests in `jl-cmd/claude-code-config` (primary repo).
2. Each **open or draft** pull request listed under [Pinned PR queue (JonEcho)](#pinned-pr-queue-jonecho) (dedupe if a URL ever overlaps the primary list).

Mark each converged PR ready for review with `gh pr ready <N> -R <owner>/<repo>`. Stop when every active queue item has converged or hit a hard blocker per [`SKILL.md` §Stop conditions](../SKILL.md#stop-conditions).

## Pinned PR queue (JonEcho)

Merge these URLs into Step 0 and Multitask fan-out. Parse `owner`, `repo`, and `number` from each link. When assembling the **active** converge set, include only PRs whose `gh pr view <N> -R owner/repo --json state` is `OPEN` or `DRAFT`; if merged or closed, log one line and skip.

| URL | `gh -R` | `#` |
|-----|---------|-----|
| https://github.com/JonEcho/Collections/pull/3 | `JonEcho/Collections` | 3 |
| https://github.com/JonEcho/python-automation/pull/84 | `JonEcho/python-automation` | 84 |
| https://github.com/JonEcho/python-automation/pull/85 | `JonEcho/python-automation` | 85 |
| https://github.com/JonEcho/llm-settings/pull/89 | `JonEcho/llm-settings` | 89 |
| https://github.com/JonEcho/us-paid-promotion/pull/22 | `JonEcho/us-paid-promotion` | 22 |

## Dedupe and `owner` / `repo` substitution

- **Union** primary-repo open PRs with eligible pinned rows; **dedupe** by `owner/repo#number` (same PR must not appear twice).
- **Primary repo** fixed values: `owner=jl-cmd`, `repo=claude-code-config`.
- **Everywhere** the main skill shows placeholders `<OWNER>` / `<REPO>` / `<NUMBER>`: for pinned rows substitute the parsed owner, repo, and number from the table or URL.
- **`gh pr`:** use `gh pr … -R <owner>/<repo>` everywhere a command would otherwise assume the current git remote.
- **`gh api` paths:** use `repos/<owner>/<repo>/…` (not hardcoded `jl-cmd/claude-code-config` except when listing the primary queue).
- **Python helpers** under `scripts/`: pass `--owner <owner> --repo <repo> --number <number>` on every invocation.

## Step 0: Discover work queue

At the start of each session (or after a long pause), assemble the current PR state dynamically.

**Primary repo — list open PRs:**

```bash
gh api 'repos/jl-cmd/claude-code-config/pulls?state=open&per_page=100' --paginate --slurp \
  | jq '[.[][] | {number, title, headRefName: .head.ref, head_sha: .head.sha, mergeable, isDraft: .draft}] | sort_by(.number)'
```

**Bugbot review status per queue item** (run for each `(owner, repo, number)`; primary repo uses `jl-cmd` / `claude-code-config`):

```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_reviews.py" \
  --owner <owner> --repo <repo> --number <N>
```

Returns `classification: "clean"` or `classification: "dirty"` plus `commit_id`.

**Bugbot inline findings for dirty PRs** (run for each dirty `<N>` at its `<HEAD_SHA>`):

```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_inline_comments.py" \
  --owner <owner> --repo <repo> --number <N> --commit <HEAD_SHA>
```

**Prior bugteam review per PR** (run for each `(owner, repo, number)`):

```bash
gh api 'repos/<owner>/<repo>/pulls/<N>/reviews?per_page=100' --paginate --slurp \
  | jq '[.[][] | select(.body | startswith("## /bugteam"))] | sort_by(.submitted_at) | last | {commit_id, body}'
```

A review body ending with `-> clean` at the current HEAD means bugteam passed.

**Pinned JonEcho PRs:** For each row in [Pinned PR queue (JonEcho)](#pinned-pr-queue-jonecho), if the PR is open or draft, run the **same four command patterns** substituting `<owner>`, `<repo>`, and `<N>` from the row. Use `gh pr view <N> -R <owner>/<repo> --json state,headRefOid` to confirm state and HEAD before the four steps.

Union primary-repo open PRs with eligible pinned rows (dedupe by `owner/repo#number`). Build a decision table from the combined results:

| Owner/Repo | PR | Head SHA | Bugbot | Bugteam | Next action |
|------------|----|-----------|--------|---------|---------------|
| … | … | … | clean/dirty | clean/dirty/none | … |

## Multitask Mode — `continue` fan-out

When **Multitask Mode** is active (for example in Cursor) and the user types **`continue`** (advance the convergence loop), the **coordinator** should **not** run a single-PR tick for one PR by default.

1. Build the unified `(owner, repo, number)` list: open PRs on `jl-cmd/claude-code-config` (for example `gh pr list -R jl-cmd/claude-code-config --state open --json number,url`) **plus** each open/draft row from [Pinned PR queue (JonEcho)](#pinned-pr-queue-jonecho) (verify with `gh pr view` per row). Dedupe by `owner/repo#number`.
2. For **each** tuple, spawn **one** background subagent (host-specific `Task` or equivalent) whose prompt scopes **that** PR only and requires `gh … -R <owner>/<repo>` and script args `--owner <owner> --repo <repo> --number <N>`.
3. Each worker runs **exactly one** converge tick for **that** PR: resolve HEAD, Bugbot state vs current HEAD, inline handling, and **at most one** loop advance per [`SKILL.md` §Per-tick work](../SKILL.md#per-tick-work) (load [`../bugteam/SKILL.md`](../../bugteam/SKILL.md) for BUGTEAM; do not hand-roll a second audit).

Outside Multitask Mode, `continue` still means one coordinator tick on the active PR context as today.

## Where the rest of the loop lives

- **AHK one-time setup, `caller_pid`, stop script, and “Awaiting next continue tick”** — [`ahk-auto-continue-loop.md`](ahk-auto-continue-loop.md).
- **BUGBOT / BUGTEAM phases, Step 3 `bugbot run`, Fix protocol, convergence, safety cap** — [`SKILL.md`](../SKILL.md).
