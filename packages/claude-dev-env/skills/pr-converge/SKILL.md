---
name: pr-converge
description: >-
  Drives the current PR to convergence by alternating Cursor Bugbot and the
  in-house second audit (`/bugteam` when agent teams are available, else one
  background agent per PR per §Second-audit execution). Each invocation runs one
  tick of work in the main session: fetches the latest reviewer state, applies
  TDD fixes for any findings, pushes one commit per tick, replies inline (or
  delegates fixes per §Multi-PR orchestration model), and re-triggers reviewers.
  Default behavior loops until back-to-back clean: pace the next tick with
  ScheduleWakeup when the harness exposes it, otherwise use the AHK
  auto-continue driver (see workflows/ahk-auto-continue-loop.md). Pacing details
  live in workflows next to SKILL.md — load exactly one per Step 4.
  `/loop /pr-converge` is the same loop with an explicit /loop wrapper when the
  harness or habit calls for it — not required for looping.
  Convergence requires a back-to-back clean cycle (bugbot CLEAN immediately
  followed by second-audit CLEAN with no intervening fixes), at which point the PR
  is flipped to ready for review and the loop terminates.
  Multi-PR runs persist traffic in `<TMPDIR>/pr-converge-<session_id>/state.json`
  per §Multi-PR orchestration model; single-PR-only runs may use the conversation
  state line instead. Triggers: '/pr-converge', '/loop /pr-converge', 'drive PR to
  convergence', 'loop bugbot and bugteam',
  'babysit bugbot and bugteam', 'until both are clean', 'converge this PR'.
---

# PR Converge

Each **invocation** runs **one tick** of the bugbot ↔ second-audit loop in the **parent session** (fetch state, address findings under the Fix
  protocol when needed, at most one fix commit per tick, inline replies or teammate handoffs, Bugbot re-trigger rules in Step 2 / Step 3).
  **By default** the skill **keeps going** until back-to-back clean on the same `HEAD`: after each tick, **Step 4** schedules the next tick with
  `ScheduleWakeup` when the tool exists, otherwise uses the **AHK auto-continue** driver. On convergence, mark the PR ready (`gh pr ready` or
  `mark_pr_ready.py` per §Step 2), then **stop all pacing** (omit further `ScheduleWakeup`; stop the AHK auto-typer when that fallback was in use).
  Designed to be invoked under `/loop /pr-converge` so the parent's `ScheduleWakeup` paces re-entry when the host supports it.

## Table of contents

1. [Parent session](#parent-session)
2. [Pacing workflows (load exactly one)](#pacing-workflows-load-exactly-one)
3. [State across ticks](#state-across-ticks)
4. [Per-tick work](#per-tick-work)
   - [Step 1: Resolve current HEAD and PR context](#step-1-resolve-current-head-and-pr-context)
   - [Step 2: Branch on `phase`](#step-2-branch-on-phase)
   - [Step 3: Re-trigger bugbot](#step-3-re-trigger-bugbot)
   - [Step 3.5: Enforce the safety cap](#step-35-enforce-the-safety-cap)
   - [Step 4: Loop pacing](#step-4-loop-pacing)
5. [Fix protocol](#fix-protocol)
6. [Stop conditions](#stop-conditions)
7. [Safety cap](#safety-cap)
8. [Ground rules](#ground-rules)
9. [Examples](#examples)

## Parent session

Use this skill on a **draft PR** where **Cursor Bugbot** and the **`/bugteam`** audit should **re-run after each push**, with
  **findings fixed between rounds**, until **back-to-back clean** on the same `HEAD`; then **mark the PR ready for review**.

Run **every converge tick** in the **parent harness session** (the conversation where the user invoked `/pr-converge`).
  **Loop pacing** (how the next tick is scheduled) is split into two workflow files — load **exactly one** per **Step 4**; see
  [Pacing workflows](#pacing-workflows-load-exactly-one).

This skill **complements** **`/bugteam`** (or the §Second-audit execution background-agent path when teams are absent): it sequences Bugbot
  re-reviews, second-audit runs, the Fix protocol, and inline replies or teammate handoffs between pushes until back-to-back clean. The in-house
  audit on every BUGTEAM tick when teams are present is **`/bugteam`** (bugteam skill), not a parallel substitute. **Fix protocol** production
  edits use **`Task` + `clean-coder`** per project agent files (or the clean-coder teammate in §Multi-PR orchestration model). **Loop pacing** stays
  in the **main** session when this host exposes `ScheduleWakeup`; otherwise use the AHK workflow file row below.

## Pacing workflows (load exactly one)

Before **Step 4** on each tick, decide whether **`ScheduleWakeup` is invokable** in this session (orchestrated teams / tool registry).
  **Use the Read tool** on exactly one file under the same directory as this skill's `SKILL.md` (installed copies usually live under
  `$HOME/.claude/skills/pr-converge/`):

| Route | Read this file |
| --- | --- |
| `ScheduleWakeup` available | `workflows/schedule-wakeup-loop.md` |
| `ScheduleWakeup` not available | `workflows/ahk-auto-continue-loop.md` |

All pacing-specific instructions for that route — delays, prompts, AHK setup, `continue` handling, convergence cleanup for the auto-typer,
  inline-lag pacing split, and route-only gotchas — live **only** in that workflow file. This `SKILL.md` keeps shared bugbot / second-audit / Fix
  protocol / stop rules.

- **`/pr-converge`** (default): loops until convergence. After each tick (unless converged or stopped), run **Step 4**, which starts by loading
  the correct workflow row from the table above.

## Progressive disclosure (skill folder)

This skill is a **folder** (`SKILL.md` plus `scripts/` plus `references/`), not prose alone: wrappers centralize gh pagination and body-file rules so the model composes orchestration instead of re-deriving CLI footguns. Read in this order ([Anthropic — internal patterns for Claude Code skills](https://x.com/trq212/status/2033949937936085378)):

1. This `SKILL.md` — phase graph, teammate contracts, stop conditions.
2. [`scripts/README.md`](scripts/README.md) — argv, stdout JSON shapes, pointers to `../../rules/gh-paginate.md` and `../../rules/gh-body-file.md`.
3. [`references/background-agent-second-audit.md`](references/background-agent-second-audit.md) **on demand** — load only when `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS != 1` and the BUGTEAM tick takes the non-team path.
4. Individual script source or `--help` — only when a call fails or `${CLAUDE_SKILL_DIR}` resolves unexpectedly.

Taxonomy: **CI/CD & Deployment** in the [`babysit-pr` archetype](https://x.com/trq212/status/2033949937936085378) — monitors a PR, applies fixes between reviewer ticks, and flips it ready-for-review on convergence. If the doc feels broad, use **§Multi-PR orchestration model** as the workflow spine and **§Per-tick work** as the single-PR linearization.

## Gotchas

Non-default behaviors worth burning in; add a bullet here when a real run fails in a new way ([same source](https://x.com/trq212/status/2033949937936085378)):

- **`ScheduleWakeup` is not in subagent tool registries** — a background `general-purpose` tick cannot schedule the next re-entry; only the main session under `/loop /pr-converge` owns `ScheduleWakeup`.
- **Bugbot only recognizes the literal re-trigger phrase `bugbot run`** — other comment text no-ops; prefer `trigger_bugbot.py` (temp body file) or
  the bundled `scripts/post-bugbot-run.ps1` so backticks in prose never corrupt the PR comment.
- **Review body and inline comments can desync for the same `commit_id`** — “dirty body, zero inline rows at `current_head`” is **`inline_lag`**, not **`dirty`**; bump `inline_lag_streak`, wait 60s, retry fetch (Step 2 BUGBOT fourth branch; §Fix result → general-purpose steps 4c–4e).
- **`state.json` without the §Concurrency lock loses merges** when several teammates finish in one wall-clock window.
- **`tick_count` must not double-increment** — conversation line (Step 1) only when **no** `state.json`; with `state.json`, only the orchestrator bump in §Orchestrator `state.json` writes counts toward Step 3.5.

## Second-audit execution (team vs Cursor)

The **second audit** (BUGTEAM phase) is either the `/bugteam` skill (Claude Code agent teams) or **one simple background agent per PR** (no `TeamCreate`) that must produce the **same downstream contract** as `/bugteam` for Step 2 BUGTEAM §(b)–(d): optional commits on `current_head`, convergence or findings list, same fix and re-trigger behaviour.

### Team infrastructure detection

At the start of BUGTEAM step **(a)** each tick, evaluate **once**:

- **Team infrastructure present** when the environment variable `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is set and its value equals **`1`** after trimming leading and trailing whitespace. This matches the bugteam skill's requirement for Claude Code agent teams (`packages/claude-dev-env/skills/bugteam/CONSTRAINTS.md`).
- **Otherwise** (unset, any other value, or host never exports this variable — typical Cursor IDE sessions): team infrastructure is **absent**. Do **not** invoke `Skill({skill: "bugteam", ...})` or rely on `TeamCreate`; use the **non-team background-agent** branch in BUGTEAM step **(a)** instead.

### Background-agent second audit (when team infrastructure is absent)

When the team-infrastructure check above fails, **one** simple background `general-purpose` agent per PR runs the equivalent of `/bugteam` inside its own session and returns the same outcome shape (convergence vs findings list with `file:line`). The orchestrator only spawns and waits.

Detail (preflight, gate, rubric, convergence reporting label) lives in [`references/background-agent-second-audit.md`](references/background-agent-second-audit.md). Read that file when this branch fires; do not paraphrase it from memory.

## Multi-PR orchestration model

### Core rule: orchestrator is a traffic controller only

The orchestrator (main session) **never** reads **repository source files**, writes code, audits findings, or does any per-PR **codebase** work inline. It **always** reads `state.json` for traffic state and may write only the narrow fields in §Orchestrator `state.json` writes; it receives teammate handoffs and spawns the next worker. Every unit of audit/fix work runs inside a dedicated teammate.

This is a [workflow-style skill](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#use-workflows-for-complex-tasks): the orchestrator decomposes the multi-PR problem into parallel per-PR subworkflows, each owned by a short-lived teammate. The orchestrator's only job is to keep the state file consistent and spawn the next agent in each chain.

### Per-PR state file

Create once at session start; each teammate writes its result back before going idle:

**Path:** `<TMPDIR>/pr-converge-<session_id>/state.json`

**Session ID:** `YYYYMMDDHHMMSS` captured once when the loop starts.

**Barebones schema:**

```json
{
  "session_id": "20260502050000",
  "prs": {
    "289": {
      "owner": "jl-cmd",
      "repo": "claude-code-config",
      "branch": "feat/shared-pr-loop-extraction",
      "phase": "BUGBOT",
      "current_head": "f9a7d49e",
      "bugbot_clean_at": null,
      "inline_lag_streak": 0,
      "tick_count": 5,
      "last_action": "bugbot_triggered",
      "status": "in_progress",
      "last_updated": "2026-05-02T10:00:00Z"
    }
  }
}
```

**`status` values:** `fresh` | `in_progress` | `awaiting_bugbot` | `awaiting_bugteam` | `converged` | `blocked`

**Write rule:** Teammates write their result by reading the current file, merging **only** their PR's keyed entry under `prs`, and persisting the merged document back. Writes are keyed on `pr_number`; other PRs' entries are untouched in the merge logic — **but** see **Concurrency** below so parallel teammates never clobber each other.

**Concurrency (mandatory):** When multiple teammates can finish in the same wall-clock window (including the case where **10+** idle notifications arrive together), a naive read–modify–write on `state.json` **loses updates** (two writers read the same revision; the second `write` overwrites the first). Every `state.json` update from a teammate **must** use **serialized access** plus **atomic publish**:

1. **Acquire** an exclusive lock in the same directory as `state.json`, for example a sibling path `state.json.lock` created with an **atomic create-only** primitive (`mkdir` on Unix when the path does not exist; on Windows `New-Item` / `md` guarded so only one creator succeeds, or a host file lock API). If acquisition fails because the lock exists, sleep with jitter and **retry** until held (cap retries and escalate per **Stop conditions** if the lock never clears — indicates a stuck teammate).
2. **Read** `state.json`, merge this teammate's `prs[<pr_number>]` object only, then **write** the full merged JSON to `state.json.tmp` in that directory.
3. **Replace** `state.json` atomically from `state.json.tmp` (`os.replace` / same-volume rename semantics so readers never see a half-written file).
4. **Release** the lock (`rmdir` / `Remove-Item` on the lock path).

**Orchestrator `state.json` writes (traffic metadata only):** Teammates own audit/fix payloads. The orchestrator **must not** merge finding bodies, file contents, or teammate-owned fields other than the two narrow exceptions below. It **must** use the **same §Concurrency lock** for any orchestrator write.

1. **Per-tick `tick_count` bump (mandatory):** At the **start** of each orchestrator tick, before spawning teammates for that tick, perform one locked read–merge–atomic publish: for **every** `prs[<pr_number>]` whose `status` is **not** `converged` or `blocked`, increment `tick_count` by **1** (initialize to `0` if missing) and refresh `last_updated`. Without this increment, **Step 3.5** never applies to `state.json` and the safety cap is dead.
2. **`phase` when only the orchestrator decides:** If the orchestrator applies a **Step 2 §Per-tick** phase transition (including **BUGTEAM §(d)** branches that set `phase = BUGBOT` without an immediate teammate `state.json` write) and no teammate merge occurs in the same tick for that PR, the orchestrator performs one locked merge that sets only `prs[<pr_number>].phase` (and `last_updated`) for the affected PR.

**Orchestrator reads this file at the start of every tick** instead of relying on conversation context for cross-PR state.

### Teammate spawning rules

When the orchestrator receives results from one or more PRs simultaneously (e.g. 10+ teammate idle notifications arrive together), it spawns one new agent **per PR** in a single parallel message — never processes any PR inline.

#### Audit result → clean-coder per PR

When a bugfind teammate reports completion (findings or clean):

- Spawn **one `clean-coder` agent** per PR with findings. That agent:
  1. Reads the outcomes XML for the PR.
  2. Applies TDD fixes (test first, then production code).
  3. Commits and pushes one fix commit.
  4. Replies inline to each addressed finding comment via `reply_to_inline_comment.py`.
  5. **Writes its result to `state.json`** (per §Concurrency) (`last_action: "fix_pushed"`, `current_head: <new SHA>`, `bugbot_clean_at: null`, `phase: "BUGBOT"`, `status: "awaiting_bugbot"`, `last_updated` as an ISO-8601 UTC timestamp).
  6. Goes idle.

- For PRs with zero findings: spawn **one `general-purpose` agent** per PR. That agent:
  1. If `bugbot_clean_at == current_head` (back-to-back clean): run `mark_pr_ready.py`, append one convergence row to the §Memory log at `${CLAUDE_PLUGIN_DATA}/pr-converge/converged.log`, then **write `state.json`** (per §Concurrency) setting this PR's entry to at least `status: "converged"`, `last_action: "converged"` (or `marked_ready`), `phase: "BUGBOT"`, and `last_updated` to an ISO-8601 UTC timestamp — **before** going idle. Omitting this write leaves the orchestrator on later ticks with a stale `awaiting_bugteam` / `in_progress` row and risks duplicate work.
  2. Otherwise: update `state.json` (per §Concurrency) with `last_action: "audit_clean"`, `status: "awaiting_bugbot"`, `phase: "BUGBOT"`, then trigger bugbot via `trigger_bugbot.py`.
  3. Goes idle.

#### Fix result → general-purpose per PR

When a bugfix (clean-coder) teammate goes idle after pushing a fix:

- Spawn **one `general-purpose` agent** per PR. That agent:
  1. Reads `state.json` for its PR.
  2. Triggers bugbot via `trigger_bugbot.py`.
  3. Polls `fetch_bugbot_reviews.py` every 60s (up to 10 polls) until a review anchored to `current_head` appears.
  4. **Poll / classify loop** (repeat from **4a** whenever **4c** schedules a retry):
     - **4a.** Fetches inline comments via `fetch_bugbot_inline_comments.py`.
     - **4b.** Classify — same three outcomes as Step 2 BUGBOT once a review exists at `current_head`:
       - **`clean`:** Review body indicates clean against `current_head` and zero unaddressed inline findings.
       - **`dirty`:** At least one unaddressed inline finding for `current_head` (actionable for the Fix protocol / `clean-coder`).
       - **`inline_lag`:** Review body indicates findings against `current_head`, but the inline-comments API returns zero matching comments for `current_head` (transient desync between review body and inline API — Step 2 BUGBOT fourth bullet).
     - **4c.** **If `inline_lag`:** Locked merge to `state.json` (per §Concurrency): increment `inline_lag_streak` (treat missing as `0` before increment); set `last_action: "inline_lag_wait"`, `phase: "BUGBOT"`, `last_updated`, and keep `status` consistent with monitoring (for example `awaiting_bugbot`). If `inline_lag_streak >= 3`, **hard blocker** per §Stop conditions (structurally inconsistent review); report and go idle **without** classifying as `dirty`. Otherwise sleep **60 seconds** and repeat from **4a** (re-fetch inline only — do not re-run step 2 or step 3).
     - **4d.** **If `clean`:** Exit the loop. Locked merge: set `bugbot_clean_at` to `current_head`, reset `inline_lag_streak` to `0`, update `last_action`, `status`, and **`phase`: `BUGTEAM`** (next work is second audit).
     - **4e.** **If `dirty`:** Exit the loop. Locked merge: reset `inline_lag_streak` to `0`, record findings count, update `last_action`, `status`, and **`phase`: `BUGBOT`** (next work is another fix pass).
  5. Reports back to orchestrator: one-line summary of outcome.

- Orchestrator reads the updated `state.json` and spawns the appropriate next agent:
  - Result `clean` → spawn a `general-purpose` agent to run BUGTEAM phase (invokes bugteam skill **or** §Background-agent second audit per §Second-audit execution, whichever applies at runtime).
  - Monitor exited on **`dirty` (step 4e)** with actionable inline threads → spawn a `clean-coder` agent (same as "audit result with findings" above). Do **not** spawn `clean-coder` when the monitor only saw **`inline_lag`** (4c retries) without reaching **4e** — that path retries or hits the §Stop conditions streak cap instead of a fix pass.

### What the orchestrator does per tick

1. Perform the **per-tick `tick_count` bump** in §Orchestrator `state.json` writes (traffic metadata only) for every non-terminal PR under `prs`.
2. Read `state.json`.
3. For each PR with new teammate results (idle notifications), spawn the next agent per the rules above — all in one parallel message.
4. Re-read `state.json` if needed for scheduling; **Step 3.5** uses each PR's `tick_count` from this file (or the conversation state line when no `state.json` exists — single-PR-only invocation).
5. Call `ScheduleWakeup` with the appropriate delay.
6. Nothing else.

## Memory

`state.json` is **session-scoped** (under `<TMPDIR>` and tied to a `session_id`); it is intentionally wiped between sessions and may be lost on plugin upgrade. For **cross-session history** of which PRs this skill has converged, append one line per convergence to a stable, plugin-scoped log per [Anthropic's recommendation to use `${CLAUDE_PLUGIN_DATA}` for durable skill data](https://x.com/trq212/status/2033949937936085378):

- **Path:** `${CLAUDE_PLUGIN_DATA}/pr-converge/converged.log`
- **Format:** one tab-separated row per converged PR — `<ISO8601_UTC>\t<owner>/<repo>#<number>\tbugbot=<SHA>\t<SECOND_AUDIT_LABEL>=<SHA>` where `<SECOND_AUDIT_LABEL>` is `bugteam` or `cursor_audit` per §Second-audit execution.
- **Append site:** the agent that runs `mark_pr_ready.py` (see §Audit result → general-purpose convergence branch and Step 2 BUGTEAM second branch). Append **before** `state.json` is written so the log row is durable even if the locked `state.json` write retries or fails.
- **Never read inside the loop.** This log exists for the user (and follow-up tooling) to inspect history; the orchestrator and teammates never gate behavior on its contents.

When `${CLAUDE_PLUGIN_DATA}` is unset (skill not installed via a plugin), skip the append silently — convergence still completes via `mark_pr_ready.py` and the conversation-line summary.

## Invocation modes

- **`/loop /pr-converge`** (recommended): loops automatically. The /loop skill runs each tick and uses `ScheduleWakeup` to pace re-entry. Termination on convergence is automatic; the skill omits the next wakeup at the convergence tick.
- **`/pr-converge`** (manual): runs exactly one tick and returns. Useful for ad-hoc state checks or for advancing the loop one step manually. To continue automatically, invoke `/loop /pr-converge` in Claude Code.

## State across ticks

**Dual persistence:** When `<TMPDIR>/pr-converge-<session_id>/state.json` exists (multi-PR or file-backed session per §Multi-PR orchestration model),
  the orchestrator and teammates treat **that file** as the source of truth for `phase`, heads, counters, and status — not the conversation
  transcript. When **no** `state.json` is in use (typical single-PR `/pr-converge` in Cursor), track the following **in each assistant turn as plain
  text** so the **next tick that resumes in this transcript** can re-read them from conversation context:

- `phase`: `BUGBOT` or `BUGTEAM`. Start in `BUGBOT` on the first tick of a fresh loop.
- `bugbot_clean_at`: the HEAD SHA at which bugbot last reported clean, or `null`. Reset to `null` whenever a new commit is pushed.
- `inline_lag_streak`: integer counter, initialized to `0`. Tracks consecutive ticks where bugbot's review body indicates findings against
  `current_head` but the inline-comments API returns zero matching comments. Reset to `0` on any other branch outcome.
- `tick_count`: integer, initialized to `0`. Increment on every tick to enforce the safety cap.

Each tick begins by reading the prior tick's state line from the most recent assistant message (when **no** `state.json`) and ends by emitting the
  updated state line; when `state.json` is in use, follow §What the orchestrator does per tick instead.

## Per-tick work

### Step 1: Resolve current HEAD and PR context

Read the prior tick's state line from the most recent assistant message (or initialize all fields if none). **Increment `tick_count` by 1** in the **conversation state line** when **no** `state.json` is in use (single-PR-only invocation); when `state.json` exists, **do not** increment here — the orchestrator's per-tick bump in §Orchestrator `state.json` writes is the sole increment for that store. Without a bump somewhere, the safety cap (Step 3.5, §Safety cap) never fires.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/view_pr_context.py"
```

Output is a JSON object with `number`, `url`, `headRefOid`, `baseRefName`, `headRefName`, `isDraft`. Capture `number` (`<NUMBER>`), `headRefOid` (`current_head`), owner/repo (from `url`), branch name (`<BRANCH>`).

### Step 2: Branch on `phase`

#### `phase == BUGBOT`

a. Fetch Cursor Bugbot reviews newest-first and walk backwards until the first clean review. The script enforces the gh-paginate rule (uses `--paginate --slurp` plus Python JSON handling — see [`scripts/README.md`](scripts/README.md) and [`../../rules/gh-paginate.md`](../../rules/gh-paginate.md)) and classifies each review:

   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_reviews.py" \
     --owner <OWNER> --repo <REPO> --number <NUMBER>
   ```

   Output is a JSON array of `{review_id, commit_id, submitted_at, body, classification}`, newest-first, with `classification` already set to `"dirty"` or `"clean"`. Track dirty entries in a temp file as you walk; the Fix protocol reads it back later in this tick:

   ```bash
   dirty_reviews_path=$(mktemp "${TMPDIR:-/tmp}/pr-converge-bugbot.XXXXXX")
   : > "$dirty_reviews_path"
   ```

   Iterate from index 0 (most recent) toward older entries:

   - For a dirty review, append one JSON line to `$dirty_reviews_path` with `{review_id, commit_id, submitted_at, body}`.
   - Stop at the first clean review. Older reviews are presumed addressed at that clean checkpoint and are not re-read.
   - When index 0 is itself clean, `$dirty_reviews_path` stays empty.

   Capture `commit_id`, `submitted_at`, body, and `classification` of the index-0 review for the decision branches below. When a branch routes to the **Fix protocol**, read every entry from `$dirty_reviews_path` and address all of them — not just index 0.

b. Fetch unaddressed inline comments from `cursor[bot]` on `current_head`. The script enforces the same `--paginate --slurp` pattern and filters by commit:

   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_inline_comments.py" \
     --owner <OWNER> --repo <REPO> --number <NUMBER> --commit "$current_head"
   ```

   Output is a JSON array of `{comment_id, commit_id, path, line, body}` for cursor[bot] comments anchored to `current_head`.

c. Decide (the four branches below cover every input combination — match the first branch whose predicate holds):
   - **No bugbot review yet, OR latest bugbot review's `commit_id` differs from `current_head`:** Re-trigger bugbot (Step 3), set
     `bugbot_clean_at = null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND zero unaddressed inline findings AND review body indicates clean:** Set `bugbot_clean_at
     = current_head`. Reset `inline_lag_streak = 0`. Transition `phase = BUGTEAM`. Continue to BUGTEAM in this same tick — back-to-back
     convergence requires the second audit on the same HEAD before the next wakeup is scheduled.
   - **Latest review's `commit_id == current_head` with unaddressed inline findings (review body indicates findings):** Apply the **Fix
     protocol** below. Reset `inline_lag_streak = 0`. When **`state.json`** is in use, the clean-coder teammate pushes, replies inline, writes
     `state.json`, then goes idle; **Step 3** (`trigger_bugbot.py` on the new HEAD) runs **after** via the orchestrator-spawned follow-up agent
     (§Fix result → general-purpose). When **no** `state.json` (typical single-PR Cursor tick), complete implement → push → inline replies → Step 3
     in the same tick per your loaded pacing workflow. Schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND review body indicates findings AND inline-comments API returns zero matching comments
     for `current_head`:** Treat as transient API propagation lag. Increment `inline_lag_streak`. When `inline_lag_streak >= 3`, escalate as a hard
     blocker; report and terminate with no loop pacing; stop the AHK auto-typer per `workflows/ahk-auto-continue-loop.md` if that path was active.
     Otherwise complete **Step 4** using the **BUGBOT inline-lag** section of the pacing workflow you loaded ([Pacing workflows](#pacing-workflows-load-exactly-one)); if no workflow file applies, schedule the next wakeup at `delaySeconds: 60`.

**Gotcha (Bugbot already clean on `HEAD`, but another `bugbot run` fires):** When the latest Bugbot review on `current_head` already indicates
  **clean / no issues** (the branch that sets `bugbot_clean_at` and transitions to **`phase = BUGTEAM`**), the next action must be the **second
  audit in the same tick** per §Second-audit execution — never a redundant `bugbot run`. If merged findings require commits, continue with **Fix
  protocol** using **`clean-coder`**. If `clean-coder` is unavailable, STOP and notify the user.

#### `phase == BUGTEAM`

a. Run the **second audit** on the current PR. Branch on §Team infrastructure detection:

   - **Team path** (team infrastructure **present**): invoke the `Skill` tool in the main session:

     ```
     Skill({skill: "bugteam", args: "https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"})
     ```

     **Orchestrated teams available:** the main session may act as team lead and `TeamCreate` may run from the orchestrator alongside `/bugteam`
     teammate spawn lines and audit progress. **No team / orchestration compatibility:** `/bugteam` still runs via `Skill` — expect CODE_RULES
     gate output and audit progress, but do **not** assume `TeamCreate` where the host does not provide it. Wait for completion; capture exit and
     final summary.

   - **Non-team path** (team infrastructure **absent**): spawn **one** simple **background** `general-purpose` agent per PR whose prompt is the
     contract in [`references/background-agent-second-audit.md`](references/background-agent-second-audit.md) (loaded on-demand for this branch).
     Wait until it completes (join or completion notification, per host). Capture the same class of summary you would from `/bugteam` (convergence
     vs findings) for Step **(c)**. The orchestrator does not perform that audit inline.

b. **Re-resolve current HEAD now** because the second audit may have pushed commits during its run. The `current_head` from Step 1 is potentially
  stale at this point:
   ```bash
   new_head=$(python "${CLAUDE_SKILL_DIR}/scripts/resolve_pr_head.py" \
     --owner <OWNER> --repo <REPO> --number <NUMBER>)
   ```
   If `new_head != current_head`, set `current_head = new_head` AND set `bugbot_clean_at = null`. The new commits invalidate bugbot's prior clean.

c. Inspect the second audit output. It reports either `convergence (zero findings)` or a list of unfixed findings with file:line (same semantics as `/bugteam`).

d. Decide based on the (post-second-audit) state — order matters; check pushed-during-second-audit FIRST so a convergence report against a stale HEAD never falsely terminates:
   - **Second audit pushed during this tick (i.e., `bugbot_clean_at` was just reset to `null` in step b):** Re-trigger bugbot in this same tick (Step 3) so the new HEAD enters bugbot's queue immediately, transition `phase = BUGBOT`, schedule next wakeup, return.
   - **Second audit reports convergence AND `bugbot_clean_at == current_head` (no push during this tick):** This is back-to-back clean. Prefer:
     ```bash
     python "${CLAUDE_SKILL_DIR}/scripts/mark_pr_ready.py" \
       --owner <OWNER> --repo <REPO> --number <NUMBER>
     ```
     When scripts are unavailable, `gh pr ready <NUMBER> --repo <OWNER>/<REPO>` is an equivalent human-visible outcome. Append the convergence row to `${CLAUDE_PLUGIN_DATA}/pr-converge/converged.log` per §Memory. Report: `PR #<NUMBER> converged: bugbot CLEAN at <SHA>, <SECOND_AUDIT_LABEL> CLEAN at <SHA>; marked ready for review` where `<SECOND_AUDIT_LABEL>` is **`bugteam`** if the team path ran or **`cursor audit`** if the background-agent path ran. **Omit loop pacing** per the **Convergence** section of whichever pacing workflow was active.
   - **Second audit reports convergence BUT `bugbot_clean_at != current_head` (no push during this tick):** Transition `phase = BUGBOT`, schedule next wakeup, return.
   - **Second audit reports findings without committing fixes:** apply the **Fix protocol** below; **Step 3** on the new HEAD runs after fix handoff per §Multi-PR or in-tick for single-PR. Transition `phase = BUGBOT`, schedule next wakeup, return.

### Step 3: Re-trigger bugbot

Used in Step 2 BUGBOT branch 1, in Step 2 BUGTEAM branch 1, and in the Fix protocol. Prefer the portable script (temp body file, `gh pr comment --body-file`):

```bash
python "${CLAUDE_SKILL_DIR}/scripts/trigger_bugbot.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER>
```

**Bundled PowerShell alternative** (same gh-body-file contract):

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" "https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"
```

Shorthand `owner/repo#number`:

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" "<OWNER>/<REPO>#<NUMBER>"
```

Explicit repository and number:

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" -Repository "<OWNER>/<REPO>" -Number <NUMBER>
```

`bugbot run` is empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

### Step 3.5: Enforce the safety cap

Before scheduling the next wakeup, evaluate **`tick_count`**: for multi-PR runs, when **any** `prs[<pr_number>].tick_count >= 30`; for single-PR-only runs (no `state.json`), when the conversation state line's `tick_count >= 30`. When the cap trips, stop and report per the **Stop conditions** safety-cap branch (§Safety cap) — **omit Step 4 entirely**. Reaching this many rounds means something structural is wrong with the loop and continuing wastes work. Otherwise proceed to Step 4.

If you cannot run the scripts above, use the Write tool to a temp file, then `gh pr comment <NUMBER> --repo <OWNER>/<REPO> --body-file <path>` yourself.
  The body file must contain exactly the literal phrase `bugbot run` followed by a newline — empirically the only re-trigger Cursor Bugbot
  recognizes; alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

**Gotcha (duplicate `bugbot run` while a review is already queued):** Do not post another `bugbot run` when Bugbot has already picked up the
  latest trigger. On GitHub, the signal is an **eyes** (`:eyes:`) reaction on the **most recent** `bugbot run` PR comment (Bugbot acknowledging
  the job). When that reaction is present, skip Step 3 for this wait cycle - a second comment spams the PR and can confuse tick logic; wait for
  the review to finish or for `HEAD` to change before re-triggering per Step 2.

**Skip Step 3.5 / Step 4 scheduling when the skill was invoked as bare `/pr-converge`** (manual mode) where the host exposes no `ScheduleWakeup` tool: there is nothing to call; one tick ends without automatic re-entry. References elsewhere in this document to "schedule next wakeup, return" mean Step 4 below; when Step 4 is skipped, every such reference becomes "return" only.

Detect **loop mode** (Step 4 eligible) only when **both** hold: the host supports `ScheduleWakeup`, **and** the run was triggered by the parent's `/loop` wakeup chain or the user typed `/loop /pr-converge`. When the most recent user message was bare `/pr-converge` (no `/loop` prefix and no such wakeup chain), or when `ScheduleWakeup` is unavailable, treat as **manual mode** for Step 4.

**Gotcha (Bugbot found errors, but a redundant `bugbot run` instead of a fix push):** When the latest Bugbot review on `current_head` still has
  **unaddressed findings** (inline threads and/or a non-clean review body), **do not** post another `bugbot run` on that same SHA as a
  substitute for fixing the code. A second trigger without a new commit cannot resolve the findings — it only duplicates noise and breaks tick
  expectations. Follow the **Fix protocol** end-to-end: spawn **`Task`** with **`subagent_type: "clean-coder"`** (never `generalPurpose` for
  production edits), **commit and push** with mandatory pre-commit and pre-push hook validation (full stop and notify the user if hooks did not
  run or were bypassed), reply inline on each thread, **then** Step 3 `bugbot run` against the new SHA.

### Step 4: Loop pacing

**`ScheduleWakeup` field hints** (when not using the workflow files — not recommended; prefer [Pacing workflows](#pacing-workflows-load-exactly-one)):

- `delaySeconds: 270` whenever bugbot was just re-triggered (whether by Step 3 directly, by **Step 3** after a fix via the follow-up agent chain, or by BUGTEAM branch 1's same-tick re-trigger). Bugbot finishes a review in 1–4 minutes, so 270s stays under the 5-minute prompt-cache TTL while giving a margin past bugbot's typical upper bound. The single exception is the BUGBOT inline-lag branch, which uses `delaySeconds: 60` because no re-trigger fired and the only thing being awaited is GitHub's inline-comments API catching up.
- `reason`: one short sentence on what is being awaited, including the current `phase` and `bugbot_clean_at` SHA when set.
- `prompt: "/loop /pr-converge"` — re-enters this skill via /loop on the next firing.

Throughout Step 2 and the Fix protocol, **schedule next wakeup, return** means: load the correct pacing workflow (see
  [Pacing workflows](#pacing-workflows-load-exactly-one)), then execute **Step 4** exactly as that file specifies (pace the next tick, then
  return).

**Entry paths** include `/pr-converge`, an AHK `continue` tick, or a `ScheduleWakeup` whose `prompt` is `/pr-converge`.

**On convergence:** apply the **Convergence** section of the **same** pacing workflow file you are using for this session (omit wakeups / stop
  AHK per that file).

## Fix protocol

The fix protocol is executed by a **`clean-coder` teammate** when **`state.json`** drives the session (§Multi-PR orchestration model), or by **`Task` + `clean-coder`** in the **main session** when **no** `state.json` is in use (typical single-PR Cursor). The orchestrator **never** performs production edits inline in multi-PR mode. Pre-commit and pre-push hook handling is governed by §Ground rules and the gates below.

**Multi-PR (`state.json`) teammate obligations** (in addition to TDD, commit, push):

- Replies inline on each addressed finding thread via `reply_to_inline_comment.py` (what changed and the commit identifier), matching §Audit result → clean-coder step 4 — **before** writing `state.json` and going idle.
- Writes `last_action: "fix_pushed"`, `current_head: <new SHA>`, `bugbot_clean_at: null`, `phase: "BUGBOT"`, `status: "awaiting_bugbot"`, and `last_updated` (ISO-8601 UTC) to `state.json` (per §Concurrency).
- Goes idle. The orchestrator spawns the follow-up `general-purpose` agent for bugbot trigger and monitoring.

**The orchestrator does not reply to inline comments, does not trigger bugbot, and does not read repository source files during the fix phase** when the multi-PR model is active.

**Single-PR (no `state.json`) — same gates, main session executor:**

- Read each referenced file:line.
- Write a failing test first when the finding has behavior to test. For pure doc, comment, or naming nits with no behavior, go straight to the fix.
- **Implement** by invoking **`Task`** with **`subagent_type: "clean-coder"`** (and the same model or harness your repo documents for that agent). Do **not** use `generalPurpose` or ad-hoc shell edits for production code in this path. If `clean-coder` is unavailable, **full stop** and tell the user — do not substitute another subagent silently.
- Stage the affected files and create one new commit on the existing branch:
  ```bash
  git add <files> && git commit -m "fix(review): <brief summary>"
  ```
  **Pre-commit gate:** Never pass `--no-verify`, `--no-gpg-sign` (unless the user has explicitly required otherwise), or any flag that skips hooks. After `git commit`, confirm from the **same terminal transcript** that the **pre-commit** hook ran (visible hook output or your configured hook runner's success banner) and exited **0**. If the transcript shows hooks were **skipped**, **bypassed**, or **did not run** when your repo expects them, **full stop** — do not push, do not reply inline, do not trigger Bugbot — and notify the user with what you observed. When a hook **rejects** (non-zero exit), read the message, fix the cause, retry commit until hooks pass.
- Push the new commit:
  ```bash
  git push origin <BRANCH>
  ```
  **Pre-push gate:** Never pass `--no-verify` or equivalent. After `git push`, confirm from the **same terminal transcript** that **pre-push** ran (when your repo defines a pre-push hook) and exited **0**. If push output shows pre-push was **skipped**, **bypassed**, or **absent** when it should have run, **full stop** — do not update `current_head`, do not reply inline, do not trigger Bugbot — and notify the user. Capture the new HEAD SHA only after both gates pass. Set `current_head` to it. Set `bugbot_clean_at = null`.
- Reply inline on each addressed comment thread using `--body-file` (per gh-body-file rule):
  ```bash
  gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments/<comment_id>/replies \
    --field body=@<path/to/reply.md>
  ```
- **After pushing a fix, always run Step 3 (`bugbot run`) in the same tick** when you would otherwise wait for Bugbot — regardless of which phase originated the findings. Step 3 is the **mechanism** that restarts Bugbot on the new `HEAD`, but the **meaning** is broader: a new commit **resets the full convergence cycle**. Prior bugbot clean and prior second-audit clean on an older SHA **do not** count toward convergence on the new `HEAD`. You must **again** obtain **bugbot CLEAN** on `current_head`, then **second-audit CLEAN** on that same `HEAD` with **no intervening push** (the same back-to-back rule as Step 2). Re-triggering Bugbot in the same tick after the push saves a full wakeup cycle compared to deferring Step 3 to the next tick.

## Stop conditions

- **Convergence** (back-to-back clean — second audit reports convergence AND `bugbot_clean_at == current_head` with no push during this tick): prefer `mark_pr_ready.py`; when unavailable use `gh pr ready`. Append `${CLAUDE_PLUGIN_DATA}/pr-converge/converged.log` per §Memory when the plugin path is set. Report one-sentence summary, then **omit loop pacing** per **Convergence** in the pacing workflow from the Step 4 table (or omit `ScheduleWakeup` when no workflow file applies). End any ongoing loops once all PRs are converged.
- **Hard blocker:** API auth failure persists across two ticks, a CI regression whose root cause falls outside this PR, a hook rejection investigated through three commits and still unresolved, `inline_lag_streak >= 3`, or the second audit (`/bugteam` or background-agent pass) reports a stuck state. Report the specific blocker and the diagnosis, then **omit loop pacing** per the active workflow; stop the AHK auto-typer per `workflows/ahk-auto-continue-loop.md` **Stop / safety** if that path was in use.
- **User stops the loop:** user says "stop the converge loop" → **omit loop pacing** per the active workflow; stop the AHK auto-typer per `workflows/ahk-auto-continue-loop.md` **Stop / safety** if that path was in use.
- **Safety cap:** any tracked `tick_count >= 30` (evaluated in Step 3.5) → **omit loop pacing** per the active workflow; stop the AHK auto-typer per `workflows/ahk-auto-continue-loop.md` **Stop / safety** if that path was in use; report the cap was hit. See §Safety cap below for rationale.

## Safety cap

When `tick_count >= 30`, stop and report. That many rounds means something structural is wrong with the loop. (Higher than copilot-review's 20-tick cap because two reviewers run sequentially per round.) **Increment:** Step 1 conversation line when **no** `state.json`; otherwise §Orchestrator `state.json` writes item 1 only. **Evaluation:** Step 3.5.

## Ground rules

- **Append commits.** Each tick adds at most one new fix commit. Multiple findings within one tick collapse into a single commit; the next tick handles the next round.
- **Bugbot findings on the current SHA mean fix-then-push-then-`bugbot run`, not another naked `bugbot run`.** Unaddressed Bugbot errors require the Fix protocol before Step 3; posting `bugbot run` again without a new commit does not clear the review state.
- **`bugbot_clean_at` resets on every push.** A new commit invalidates bugbot's prior clean by definition — bugbot must re-review the new HEAD before convergence can be claimed.
- **Back-to-back clean is the ONLY termination criterion.** Convergence requires Bugbot clean and the second audit (bugteam or background-agent pass) clean against the same HEAD with no intervening fixes; either side clean alone counts as in-progress.
- **Clean Bugbot on `HEAD` means advance to second audit, not another `bugbot run`.** After Bugbot reports clean on the current SHA, set `bugbot_clean_at` and run the BUGTEAM phase per Step 2 — never post `bugbot run` as a substitute.
- **The `bugbot run` comment is load-bearing.** Use the literal phrase `bugbot run` exactly — empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings silently no-op.
- **`gh pr ready` / `mark_pr_ready.py` is the convergence action.** Mark the PR ready for review and stop there. Merge, additional reviewers, title, and body remain the user's decisions; the skill's contract ends at "ready for review."
- **Honor pre-push and pre-commit hooks.** When a hook rejects the change, read its output, fix the underlying issue (the failing test, the missing constant, the broken import), and retry.
- **Adapt when reality contradicts on-disk state.** This skill is a state machine, but the spec assumes `state.json` (when used) and `git`/`gh` agree with the live PR. When they diverge — the user pushed manually between ticks, the branch was force-reset, the worktree moved, the PR was closed/merged externally, or `gh` auth dropped mid-tick — **do not execute the spec literally against stale state**. Report the specific drift and escalate as a hard blocker per §Stop conditions; let the user decide whether to reset the loop, refresh credentials, or stop.

## Examples

<example>
User: `/pr-converge`
Claude: [PR context + one bugbot tick; reads pacing workflow from Step 4 table; applies that file's Step 4 rules]
</example>

<example>
User: `/loop /pr-converge`
Claude: [same as `/pr-converge` default loop — one tick, then Step 4 per loaded pacing workflow]
</example>

<example>
Tick fires in BUGBOT phase, latest bugbot review is against an older commit.
Claude: [posts `bugbot run` comment, sets `bugbot_clean_at = null`, completes Step 4 per `workflows/schedule-wakeup-loop.md` when on that path
  (e.g. 270s wakeup), returns]
</example>

<example>
Tick fires in BUGBOT phase, bugbot has 2 unaddressed findings on HEAD.
Claude: [TDD-fixes both, one commit, pushes, replies inline on both threads, posts `bugbot run`, Step 4 per schedule-wakeup workflow at 270s
  when on that path, returns]
</example>

<example>
Tick fires in BUGBOT phase, bugbot is clean against HEAD.
Claude: [sets `bugbot_clean_at = HEAD`, transitions `phase = BUGTEAM`, runs `/bugteam` in the same tick]
</example>

<example>
In BUGTEAM phase, /bugteam reports convergence and `bugbot_clean_at == current_head`.
Claude: [runs `gh pr ready <NUMBER>`, reports "PR converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for review", applies
  **Convergence** from the active pacing workflow]
</example>

<example>
In BUGTEAM phase, /bugteam pushed a fix commit during its run.
Claude: [re-resolves HEAD, sets `bugbot_clean_at = null`, posts `bugbot run` in this same tick, transitions `phase = BUGBOT`, Step 4 per
  schedule-wakeup workflow at 270s when on that path]
</example>

<example>
Tick fires in BUGBOT phase, bugbot review body says "found 3 potential issues" against HEAD but the inline-comments API returns zero matching
  comments for `current_head`.
Claude: [increments `inline_lag_streak` to 1, Step 4 inline-lag rules from the active pacing workflow (60s `ScheduleWakeup` vs AHK cadence),
  returns; expects inline comments on the next tick]
</example>

<example>
BUGTEAM tick with no agent teams: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is unset; team infrastructure absent.
Claude: [loads `references/background-agent-second-audit.md`, spawns one background `general-purpose` agent with that file as the prompt, waits for handoff, applies Step 2 §(b)–(d) unchanged against that agent's outcome]
</example>
