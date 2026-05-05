---
name: cm-pr-converge
description: >-
  Drives current PR to convergence by alternating Cursor Bugbot and second
  audit (**bugteam** always — `Skill({skill: "bugteam", ...})` when host
  exposes `Skill`; bugteam **Path routing** picks Path A vs Path B from
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`; per-path harness in
  `bugteam/reference/workflow-path-a-orchestrated-teams.md` and
  `bugteam/reference/workflow-path-b-task-harness.md`). Each invocation runs
  one tick in main session: fetches latest reviewer state, applies TDD fixes
  for findings, pushes one commit per tick, replies inline (or delegates per
  §Multi-PR orchestration model), re-triggers reviewers. Default loops until
  back-to-back clean: pace next tick with ScheduleWakeup when harness exposes
  it, else AHK auto-continue driver (workflows/ahk-auto-continue-loop.md).
  Pacing details in workflows next to SKILL.md — load exactly one per Step 4.
  Convergence requires four gates on same HEAD: (1) back-to-back clean cycle
  (bugbot CLEAN immediately followed by second-audit CLEAN, no intervening
  fixes), (2) no outstanding Copilot reviewer findings, (3) `mergeStateStatus
  == CLEAN` with `mergeable == MERGEABLE` (`DIRTY` triggers `rebase` skill;
  non-CLEAN non-DIRTY states are hard blockers), (4) post-convergence Copilot
  review request returns clean — or surfaces findings: PR flipped ready,
  follow-up draft PR opened off converged HEAD with findings as checklist.
  After all gates pass PR flipped ready, loop terminates. Multi-PR runs
  persist traffic in `<TMPDIR>/pr-converge-<session_id>/state.json`;
  single-PR runs use conversation state line. Triggers: '/pr-converge',
  'drive PR to convergence', 'loop bugbot and bugteam', 'babysit bugbot and
  bugteam', 'until both are clean', 'converge this PR'.
---

# PR Converge

Each **invocation** runs **one tick** of bugbot ↔ second-audit loop in **parent
session**. Fetch state, fix via Fix protocol, max one fix commit per tick,
inline replies or teammate handoffs, Bugbot re-trigger per Step 2 / Step 3.
**Default** loops until back-to-back clean on same `HEAD`. **Step 4** schedules
next tick with `ScheduleWakeup` when tool exists, else **AHK auto-continue**
driver. On convergence, mark PR ready (`gh pr ready` or `mark_pr_ready.py` per
§Step 2), then **stop all pacing** (omit further `ScheduleWakeup`; stop AHK
auto-typer when fallback was in use). Default entry **`/pr-converge`**.
`ScheduleWakeup` uses `prompt: "/pr-converge"` unless harness requires `/loop`
wrapper (`workflows/schedule-wakeup-loop.md`).

## Table of contents

1. [Parent session](#parent-session)
2. [Pacing workflows (load exactly one)](#pacing-workflows-load-exactly-one)
3. [State across ticks](#state-across-ticks)
4. [Per-tick work](#per-tick-work)
   - [Step 1 — HEAD and PR context](#step-1-resolve-current-head-and-pr-context)
   - [Step 2: Branch on `phase`](#step-2-branch-on-phase)
   - [Convergence gates](#convergence-gates)
   - [Step 3: Re-trigger bugbot](#step-3-re-trigger-bugbot)
   - [Step 4: Loop pacing](#step-4-loop-pacing)
5. [Fix protocol](#fix-protocol)
6. [Stop conditions](#stop-conditions)
7. [Ground rules](#ground-rules)
8. [Examples](#examples)

## Parent session

Use on **draft PR**. Cursor Bugbot and `/bugteam` re-run after each push. Fix
findings between rounds until back-to-back clean on same `HEAD`, then mark
PR ready for review.

Run every tick in parent harness session. Pacing split into two workflow
files — load exactly one per Step 4; see [Pacing
workflows](#pacing-workflows-load-exactly-one).

Sequences Bugbot re-reviews, second-audit runs, Fix protocol, inline
replies or teammate handoffs until back-to-back clean. Every BUGTEAM tick
runs **bugteam** — never hand-rolled substitute. Fix protocol production
edits in main Cursor session use `Task` with `subagent_type:
"generalPurpose"` plus clean-coder **Read** preamble in `prompt` (see [Fix
protocol](#fix-protocol)) — Cursor rejects `subagent_type: "clean-coder"`.
With `state.json` driving multi-PR orchestration, `clean-coder` teammate
path unchanged. Pacing stays in main session when host exposes
`ScheduleWakeup`; else AHK workflow.

## Pacing workflows (load exactly one)

Before Step 4, only parent session (not `Task` / `Explore` child) picks one
workflow row, then **Read** that row's file next to `SKILL.md` (installed
copies under `$HOME/.claude/skills/pr-converge/`):

1. Open tool inventory for this turn — every function/tool name harness
   allows in this message (catalog includes `Read`, `Task`, shell tool).
2. `ScheduleWakeup` invokable if catalog contains top-level callable named
   exactly `ScheduleWakeup`. Indirect gateways (e.g. `call_mcp_tool` with
   server-qualified MCP tools) do **not** count. When in doubt, not invokable.
3. Pick row — invokable → available; else not available (missing / empty /
   unreadable catalogs **fail closed** to AHK; do **not** attempt
   `ScheduleWakeup`).

| Route | Read this file |
| --- | --- |
| `ScheduleWakeup` available | `workflows/schedule-wakeup-loop.md` |
| `ScheduleWakeup` not available | `workflows/ahk-auto-continue-loop.md` |

Route-specific instructions — delays, prompts, AHK setup, `continue` handling,
convergence cleanup, inline-lag split, route gotchas — live **only** in workflow
file. `SKILL.md` holds shared bugbot / second-audit / Fix protocol / stop rules.

- **`/pr-converge`** (default): loops until convergence. After each tick
  (unless converged or stopped), run **Step 4**.

## Progressive disclosure (skill folder)

Folder skill (`SKILL.md` + `scripts/` + `workflows/`). Read in order:

1. `SKILL.md` — phase graph, teammate contracts, stop conditions.
2. [`scripts/README.md`](scripts/README.md) — argv, stdout JSON, pointers
   to `../../rules/gh-paginate.md` and `../../rules/gh-body-file.md`.
3. Bugteam **Path B** harness (**on demand**): after **Path routing** picks
   Path B, read [`workflow-path-b-task-harness.md`][path-b]. Path A:
   [`workflow-path-a-orchestrated-teams.md`][path-a].
4. Script source / `--help` — only when call fails or `${CLAUDE_SKILL_DIR}`
   resolves unexpectedly.

[path-b]: ../bugteam/reference/workflow-path-b-task-harness.md
[path-a]: ../bugteam/reference/workflow-path-a-orchestrated-teams.md

Taxonomy: **CI/CD & Deployment** / `babysit-pr`. **§Multi-PR orchestration
model** = spine; **§Per-tick work** = single-PR linearization.

## Gotchas

Non-default behaviors; add bullet when real run fails in new way ([same
source](https://x.com/trq212/status/2033949937936085378)):

- **`ScheduleWakeup` not in subagent tool registries** — background
  `general-purpose` tick cannot schedule re-entry; only parent session with
  `ScheduleWakeup` in registry can call it.
- **Bugbot only recognizes literal phrase `bugbot run`** — other text no-ops.
  Prefer `trigger_bugbot.py` (temp body file) or bundled
  `packages/claude-dev-env/skills/pr-converge/scripts/post-bugbot-run.ps1` so
  backticks in prose never corrupt PR comment.
- **Review body and inline comments desync for same `commit_id`** — "dirty
  body, zero inline rows at `current_head`" is **`inline_lag`**, not
  **`dirty`**. Bump `inline_lag_streak`, wait 60s, retry fetch (Step 2 BUGBOT
  fourth branch; §Fix result → general-purpose steps 4c–4e).
- **`state.json` without §Concurrency lock loses merges** when teammates
  finish in same wall-clock window.
- **`tick_count` must not double-increment** — conversation line (Step 1)
  only when **no** `state.json`; with `state.json`, only orchestrator bump
  increments.
- **Back-to-back clean necessary but not sufficient — `mergeStateStatus` gates
  ready flip.** PR can be back-to-back clean (bugbot CLEAN ∧ bugteam CLEAN at
  same HEAD) yet still have merge conflicts with base branch. Before flipping
  ready, run `check_pr_mergeability.py` and confirm `mergeStateStatus ==
  "CLEAN"` AND `mergeable == "MERGEABLE"`. When `mergeStateStatus == "DIRTY"`
  (or `mergeable == "CONFLICTING"`), invoke **`rebase`** skill
  ([`../rebase/SKILL.md`](../rebase/SKILL.md), Phase 1–4). After successful
  rebase + force-with-lease push, new HEAD invalidates prior clean state —
  reset `bugbot_clean_at = null`, `copilot_clean_at = null`, transition
  `phase = BUGBOT`, retrigger bugbot, schedule next tick. Non-`CLEAN`
  non-`DIRTY` states (`BLOCKED`, `BEHIND`, `UNKNOWN`) are hard blockers per
  §Stop conditions.
- **Copilot findings on `current_head` block convergence** — Copilot
  (`copilot-pull-request-reviewer[bot]`) evaluated *after* bugbot CLEAN ∧
  bugteam CLEAN at same HEAD. When `fetch_copilot_reviews.py` returns review
  at `current_head` with `state == "CHANGES_REQUESTED"` (or `state ==
  "COMMENTED"` with non-empty body) and unaddressed inline findings from
  `fetch_copilot_inline_comments.py`, treat as Fix protocol input (same shape
  as bugbot dirty): TDD fix → push → reply inline → reset `bugbot_clean_at =
  null` AND `copilot_clean_at = null` → `phase = BUGBOT` → retrigger bugbot →
  schedule. Full back-to-back clean cycle must hold again. No Copilot review
  on `current_head` yet → gotcha does **not** apply; proactive request
  happens in §Convergence gates step (c).
- **Post-convergence Copilot request runs once, regardless of outcome.**
  After every other gate passes (bugbot CLEAN ∧ bugteam CLEAN ∧ no Copilot
  findings on HEAD ∧ `mergeStateStatus == "CLEAN"`), call
  `request_copilot_review.py` and wait one tick. Clean Copilot review →
  ready, terminate. Copilot review with findings on `current_head` still
  marks ready ("we still allow it to be 'clean'" rule), but before
  terminating runs `open_followup_copilot_pr.py` to capture findings as draft
  PR off `current_head`. Follow-up PR runs own `/pr-converge` cycle (queued
  for user — never inline-spawn another loop in same session). Reviewer ID
  literal: `copilot-pull-request-reviewer[bot]` with `[bot]` suffix —
  `Copilot`, `copilot`, `github-copilot` all silently no-op per
  [`../copilot-review/SKILL.md`](../copilot-review/SKILL.md).

## Second-audit execution (bugteam — Path A vs Path B)

**Second audit** (BUGTEAM phase) is **always** **bugteam** skill: preflight,
CODE_RULES gate, **`code-quality-agent`** / **`clean-coder`** loop, audit
rubric, outcome shape, Step 2 BUGTEAM §(b)–(d) contract — all in
[`../bugteam/SKILL.md`](../bugteam/SKILL.md) plus `PROMPTS.md` / `EXAMPLES.md` /
`CONSTRAINTS.md`. Do not re-spec.

**Path routing bugteam-internal:** [bugteam `SKILL.md` — Path
routing](../bugteam/SKILL.md#path-routing-mandatory-first-branch)
(`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` == **`1`** → Path A orchestrated teams;
else → Path B Task harness). Harness docs: Path A —
[`../bugteam/reference/workflow-path-a-orchestrated-teams.md`](../bugteam/reference/workflow-path-a-orchestrated-teams.md); Path B —
[`../bugteam/reference/workflow-path-b-task-harness.md`](../bugteam/reference/workflow-path-b-task-harness.md).

**pr-converge rule:** Prefer **`Skill({skill: "bugteam", args: "<PR URL or
args>"})`** wherever registry exposes `Skill` — bugteam picks path. When
`Skill` not invokable (typical delegated teammate), worker runs **bugteam**
by loading `../bugteam/SKILL.md` from same checkout and following Path
routing plus path-b doc when Path B applies. Never replace bugteam with
hand-rolled audit.

### Team infrastructure detection (pr-converge pacing and docs cross-links only)

Mirrors bugteam **Path routing**:

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS == 1` → bugteam **Path A** when
  `/bugteam` runs inside Claude Code with teams.
- Else → bugteam **Path B** Task harness inside same bugteam contract.

## Multi-PR orchestration model

When `state.json` exists at `<TMPDIR>/pr-converge-<session_id>/state.json`,
this skill runs in **multi-PR orchestrator mode**: main session becomes a
traffic controller (no inline source reads, no audits, no fixes — only state
reads, narrow state writes, teammate handoffs).

Full model in
[`reference/multi-pr-orchestration.md`](reference/multi-pr-orchestration.md):
§Per-PR state schema, §Concurrency lock contract, §Orchestrator `state.json`
writes, §Orchestrator team lifecycle (Path A only), §Teammate spawning rules
(§Audit result → fix worker per PR, §Fix result → general-purpose per PR),
§What orchestrator does per tick, §Memory (run directory, `converged.log`).

Single-PR runs (no `state.json`) ignore this section — see [State across
ticks](#state-across-ticks).

## Invocation modes

- **`/pr-converge`** (default): runs one tick, then Step 4 per [Pacing
  workflows](#pacing-workflows-load-exactly-one). Same
  loop-until-convergence semantics whether user typed once,
  `ScheduleWakeup` fires with `prompt: "/pr-converge"`, or AHK sends
  `continue`. Omit next wakeup only on convergence or **Stop conditions**.
- **`/loop /pr-converge`**: optional harness wrapper when parent only
  executes wakeup `prompt`s through `/loop`. Equivalent to default. Use
  `prompt: "/loop /pr-converge"` in `ScheduleWakeup` only when wrapper
  required.

## State across ticks

**Dual persistence:** `<TMPDIR>/pr-converge-<session_id>/state.json`
exists (multi-PR) → that file is source of truth for `phase`, heads,
counters, status, not conversation transcript. No `state.json` (typical
single-PR `/pr-converge` in Cursor) → track in each assistant turn as
plain text so next tick re-reads from context:

- `phase`: `BUGBOT` or `BUGTEAM`. Start `BUGBOT` on first tick.
- `bugbot_clean_at`: HEAD SHA where bugbot last reported clean, or `null`.
  Reset to `null` on every push.
- `inline_lag_streak`: integer, init `0`. Consecutive ticks where review
  body shows findings against `current_head` but inline API returns zero
  matching. Reset to `0` on any other branch outcome.
- `tick_count`: integer, init `0`. Increment every tick (observability;
  no ceiling).

Tick begins reading prior state line from most recent assistant message
(no `state.json`) and ends by emitting updated state line; with
`state.json`, follow `reference/multi-pr-orchestration.md` §What orchestrator does per tick.

## Per-tick work

### Step 1: Resolve current HEAD and PR context

Read prior tick's state line from most recent assistant message (or
initialize fields if none). Increment `tick_count` by 1 in conversation
state line when **no** `state.json` (single-PR only). With `state.json`, do
**not** increment here — orchestrator's per-tick bump is sole increment.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/view_pr_context.py"
```

Output: JSON with `number`, `url`, `headRefOid`, `baseRefName`,
`headRefName`, `isDraft`. Capture `number` (`<NUMBER>`), `headRefOid`
(`current_head`), owner/repo (from `url`), branch name (`<BRANCH>`).

### Step 2: Branch on `phase`

#### `phase == BUGBOT`

a. Fetch Cursor Bugbot reviews newest-first, walk back until first clean.
Script enforces gh-paginate rule (`--paginate --slurp` + Python JSON; see
[`scripts/README.md`](scripts/README.md) and
[`../../rules/gh-paginate.md`](../../rules/gh-paginate.md)) and classifies
each review:

   ```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_reviews.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
   ```

Output: JSON array of `{review_id, commit_id, submitted_at, body,
classification}`, newest-first, `classification` already `"dirty"` or
`"clean"`. Track dirty entries in temp file; Fix protocol reads it back
later this tick:

   ```bash
dirty_reviews_path=$(mktemp "${TMPDIR:-/tmp}/pr-converge-bugbot.XXXXXX")
: > "$dirty_reviews_path"
   ```

Iterate from index 0 (most recent) toward older:

   - Dirty review → append JSON line with `{review_id, commit_id,
     submitted_at, body}`.
   - Stop at first clean. Older reviews presumed addressed at that
     checkpoint.
   - Index 0 clean → `$dirty_reviews_path` stays empty.

Capture `commit_id`, `submitted_at`, body, `classification` of index-0
review for decisions below. When branch routes to **Fix protocol**, address
**every** entry in `$dirty_reviews_path` — not just index 0.

b. Fetch unaddressed inline comments from `cursor[bot]` for newest Bugbot
review on `current_head`. Script uses same `--paginate --slurp` pattern,
resolves review via reviews list, returns only inline rows whose
`pull_request_review_id` matches that review (excludes stale threads from
older reviews on same SHA).

   ```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_inline_comments.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER> --commit "$current_head"
   ```

Output: JSON array of `{comment_id, commit_id, path, line, body}` for
matching inline comments.

c. Decide (four branches; match first whose predicate holds):
   - **No bugbot review yet, OR latest review's `commit_id` ≠
     `current_head`:** Re-trigger bugbot (Step 3), set `bugbot_clean_at =
     null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
   - **`commit_id == current_head` AND zero unaddressed inline AND review
     body clean:** Set `bugbot_clean_at = current_head`, reset
     `inline_lag_streak = 0`, `phase = BUGTEAM`. Continue BUGTEAM in same
     tick — back-to-back convergence requires second audit on same HEAD
     before next wakeup.
   - **`commit_id == current_head` with unaddressed inline findings:**
     Apply **Fix protocol**. Reset `inline_lag_streak = 0`. With
     `state.json`: clean-coder teammate pushes, replies inline, writes
     `state.json`, goes idle; Step 3 on new HEAD runs after via
     orchestrator-spawned follow-up agent (§Fix result → general-purpose).
     No `state.json` (single-PR Cursor): implement → push → inline replies
     → Step 3 in same tick per loaded pacing workflow. Schedule next
     wakeup, return.
   - **`commit_id == current_head` AND review body findings AND inline
     API zero matching for `current_head`:** Transient API lag. Increment
     `inline_lag_streak`. `>= 3` → hard blocker; report and terminate with
     no loop pacing; stop AHK auto-typer per
     `workflows/ahk-auto-continue-loop.md` if active. Else Step 4 uses
     BUGBOT inline-lag section of loaded pacing workflow; no workflow file
     → `delaySeconds: 60`.

**Gotcha (Bugbot already clean on `HEAD`, another `bugbot run` fires):**
Latest Bugbot review on `current_head` already clean (branch that sets
`bugbot_clean_at` and transitions to `phase = BUGTEAM`) → next action must
be **second audit in same tick** per §Second-audit execution, never a
redundant `bugbot run`. If merged findings require commits, continue with
**Fix protocol** (`Task` with `generalPurpose` and clean-coder **Read**
preamble). If `Task` cannot be invoked, STOP and notify the user.

#### `phase == BUGTEAM`

a. Run **bugteam** (second audit) on current PR.

   - **`Skill` invokable** (see [Pacing
     workflows](#pacing-workflows-load-exactly-one) tool-inventory rules):
     invoke bugteam with `Skill`. Path A vs Path B picked inside bugteam per
     [bugteam Path
     routing](../bugteam/SKILL.md#path-routing-mandatory-first-branch);
     pr-converge does not branch on `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`.

     ```
Skill({skill: "bugteam", args:
"https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"})
     ```

Wait for completion; capture exit and final summary for Step (c).

   - **`Skill` not invokable** (typical `Task` teammate): worker executes
     bugteam by reading [`../bugteam/SKILL.md`](../bugteam/SKILL.md) and,
     if Path B applies, [path-b doc][path-b]. Same loop and gates; only
     harness steps differ.

b. **Re-resolve current HEAD** — second audit may have pushed commits
during its run. `current_head` from Step 1 is potentially stale:
   ```bash
new_head=$(python "${CLAUDE_SKILL_DIR}/scripts/resolve_pr_head.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>)
   ```
If `new_head != current_head`, set `current_head = new_head` AND
`bugbot_clean_at = null`. New commits invalidate bugbot's prior clean.

c. Inspect bugteam outcome. Reports `convergence (zero findings)` or list
of unfixed findings with file:line.

d. Decide based on post-audit state — order matters. Check
pushed-during-second-audit FIRST so convergence report against stale HEAD
never falsely terminates:
   - **Audit pushed this tick (`bugbot_clean_at` reset in step b):**
     Re-trigger bugbot same tick (Step 3) so new HEAD enters queue, `phase
     = BUGBOT`, schedule next wakeup, return.
   - **Convergence AND `bugbot_clean_at == current_head` (no push):**
     Back-to-back clean — necessary, not sufficient. Run **§Convergence
     gates** to clear Copilot-findings, mergeability, post-convergence
     Copilot-request. Only when all four gates pass mark PR ready and
     **omit loop pacing** per **Convergence** of active pacing workflow.
   - **Convergence BUT `bugbot_clean_at != current_head` (no push):**
     `phase = BUGBOT`, schedule next wakeup, return.
   - **Findings without committed fixes:** apply **Fix protocol**; Step 3
     on new HEAD runs after fix handoff per `reference/multi-pr-orchestration.md` or in-tick for
     single-PR. `phase = BUGBOT`, schedule next wakeup, return.

### Convergence gates

Run **only** when Step 2 BUGTEAM reports `convergence (zero findings)` AND
`bugbot_clean_at == current_head` AND no push during bugteam tick. Gates run
in order; first failure determines next-tick behavior. Mark PR ready only
when all four pass.

#### (a) Copilot findings gate

Fetch latest Copilot reviewer (`copilot-pull-request-reviewer[bot]`) review
plus inline comments anchored to most recent Copilot review on
`current_head`:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_copilot_reviews.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>

python "${CLAUDE_SKILL_DIR}/scripts/fetch_copilot_inline_comments.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER> --commit "$current_head"
```

Decide (four branches; match first whose predicate holds):

- **`classification == "dirty"` with non-empty inline comments matching
  `pull_request_review_id`:** Fix protocol input (same shape as bugbot
  dirty). Apply Fix protocol on every inline finding (TDD test →
  production fix → push → reply inline on each thread), reset
  `bugbot_clean_at = null` AND `copilot_clean_at = null`, `phase = BUGBOT`,
  Step 3 on new HEAD, schedule next wakeup, return. Full
  back-to-back-clean cycle plus all four gates must hold again on new HEAD.
- **`classification == "dirty"` with empty inline comments matching
  `pull_request_review_id`:** Copilot posted findings only in review body
  (`CHANGES_REQUESTED` or `COMMENTED` with non-empty body, no inline
  threads). Parse body for actionable findings, apply Fix protocol using
  body excerpts (TDD test → production fix → push). Post top-level review
  reply acknowledging fixes and citing new HEAD SHA. Reset
  `bugbot_clean_at = null` AND `copilot_clean_at = null`, `phase =
  BUGBOT`, Step 3 on new HEAD, schedule next wakeup, return. Convergence
  requires full back-to-back-clean on new HEAD.
- **`classification == "clean"` (state `APPROVED`):** Set
  `copilot_clean_at = current_head`. Continue to gate (b).
- **No Copilot review on `current_head` yet:** Skip — gate (c) issues
  proactive request. Continue to gate (b).

#### (b) Mergeability gate

Resolve PR's mergeability state:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/check_pr_mergeability.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
```

Output: `{"mergeable", "mergeStateStatus", "headRefOid"}`. Persist
`mergeStateStatus` into `merge_state_status` (state line or `state.json`).
Decide:

- **`mergeStateStatus == "CLEAN"` AND `mergeable == "MERGEABLE"`:**
  Continue to gate (c).
- **`mergeStateStatus == "DIRTY"` (or `mergeable == "CONFLICTING"`):** Do
  **not** mark ready. Invoke **`rebase`** skill
  ([`../rebase/SKILL.md`](../rebase/SKILL.md)) Phase 1–4 against PR's
  base ref. After rebase + force-with-lease push, new HEAD invalidates
  every prior clean state — reset `bugbot_clean_at = null`,
  `copilot_clean_at = null`, `merge_state_status = null`, `phase = BUGBOT`,
  Step 3 on new HEAD, schedule next wakeup, return. Loop re-runs from
  scratch on new HEAD.
- **`mergeStateStatus` is `BLOCKED`, `BEHIND`, or `UNKNOWN` for
  non-conflict reasons** (required checks pending, branch behind base
  without conflicts GitHub cannot auto-resolve): **hard blocker** per
  §Stop conditions — do not invent a fix. Report specific
  `mergeStateStatus`, omit loop pacing per active workflow, stop AHK
  auto-typer if active.

#### (c) Post-convergence Copilot review request

Once gates (a) and (b) both pass (Copilot clean at `current_head` *or* no
Copilot review yet, AND `mergeStateStatus == "CLEAN"`), request Copilot
review:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/request_copilot_review.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
```

Reviewer ID literal `copilot-pull-request-reviewer[bot]` (with `[bot]`
suffix) load-bearing — `Copilot`, `copilot`, `github-copilot` all silently
no-op per [`../copilot-review/SKILL.md`](../copilot-review/SKILL.md). After
request, schedule next wakeup and return — next tick checks response.

Next tick with `phase == BUGTEAM` and prior state preserved → re-run gate
(a) first. Decide:

- **Copilot review `clean` (state `APPROVED`):** Set `copilot_clean_at =
  current_head`. Mark PR ready (`mark_pr_ready.py`), report convergence
  per §(d), terminate per §Stop conditions / Convergence.
- **Copilot review `dirty`:** Still mark current PR ready ("we still
  allow it to be 'clean'" rule — four gates: bugbot CLEAN ∧ bugteam CLEAN
  ∧ `mergeStateStatus == CLEAN` ∧ either Copilot CLEAN at HEAD or
  follow-up PR captures findings). Before terminating, build markdown
  findings file from `fetch_copilot_inline_comments.py` (one checklist
  item per finding with file:line + excerpted body), then open follow-up
  draft PR off `current_head`:

  ```bash
python "${CLAUDE_SKILL_DIR}/scripts/open_followup_copilot_pr.py" \
--owner <OWNER> --repo <REPO> \
--parent-number <NUMBER> --head "$current_head" \
--findings-file <PATH_TO_FINDINGS_MD>
  ```

Follow-up branch: `chore/copilot-followup-<NUMBER>-<short_sha>`. PR title:
`chore: address Copilot findings from PR #<NUMBER>`. Queue `/pr-converge`
on new PR for user to invoke (do **not** inline-spawn another loop in same
session). Report both PR URLs. Current PR's convergence final at original
HEAD; new PR runs own cycle.

- **No Copilot review at `current_head` yet (still propagating):**
  Schedule one more wakeup (270s when `ScheduleWakeup` available, AHK
  cadence else), re-check next tick. After three consecutive empty waits,
  escalate as hard blocker per §Stop conditions.

#### (d) Mark ready and report

Only when all four gates pass — bugbot CLEAN ∧ bugteam CLEAN ∧
`mergeStateStatus == "CLEAN"` ∧ Copilot CLEAN at HEAD (or post-convergence
request returned dirty and follow-up PR is open) — run:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/mark_pr_ready.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
```

When scripts unavailable, `gh pr ready <NUMBER> --repo <OWNER>/<REPO>` is
equivalent. With `state.json`, append convergence row to
`<TMPDIR>/pr-converge-<session_id>/converged.log` per `reference/multi-pr-orchestration.md` §Memory; else skip.
Report: `PR #<NUMBER> converged: bugbot CLEAN at <SHA>, bugteam CLEAN at
<SHA>, mergeStateStatus CLEAN, copilot <CLEAN|FOLLOWUP_PR_URL>; marked
ready for review`. **Omit loop pacing** per **Convergence** of active
pacing workflow.

### Step 3: Re-trigger bugbot

Used in Step 2 BUGBOT branch 1, Step 2 BUGTEAM branch 1, Fix protocol.
Prefer portable script (temp body file, `gh pr comment --body-file`):

```bash
python "${CLAUDE_SKILL_DIR}/scripts/trigger_bugbot.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
```

**Bundled PowerShell alternative** (same gh-body-file contract):

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" \
"https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"
```

Shorthand `owner/repo#number`:

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" \
"<OWNER>/<REPO>#<NUMBER>"
```

Explicit repository and number:

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" \
-Repository "<OWNER>/<REPO>" -Number <NUMBER>
```

`bugbot run` is empirically the only re-trigger Cursor Bugbot recognizes;
alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

If you cannot run the scripts above, use the Write tool to a temp file, then
`gh pr comment <NUMBER> --repo <OWNER>/<REPO> --body-file <path>` yourself. The
body file must contain exactly the literal phrase `bugbot run` followed by a
newline.

**Gotcha (duplicate `bugbot run` while review already queued):** Do not
post another `bugbot run` when Bugbot already picked up latest trigger.
Bugbot signal: **eyes** (`:eyes:`) reaction on most recent `bugbot run` PR
comment. Reaction present → skip Step 3 this wait cycle. Wait for review
to finish or `HEAD` to change before re-triggering per Step 2.

**Default loop:** Each tick → run Step 4 when pacing applies. Step 4
loads pacing workflow, schedules next entry. `ScheduleWakeup` default
`prompt: "/pr-converge"` (`workflows/schedule-wakeup-loop.md`); set
`prompt: "/loop /pr-converge"` when harness requires `/loop` wrapper.

`ScheduleWakeup` unavailable → Step 4 on AHK workflow row per
`workflows/ahk-auto-continue-loop.md`. No pacing mechanism active → end
tick with return only. "Schedule next wakeup, return" means run Step 4;
when Step 4 schedules nothing, treat as return only.

**Gotcha (Bugbot found errors, redundant `bugbot run` instead of fix
push):** Latest Bugbot review on `current_head` with unaddressed findings
(inline threads and/or non-clean body) → do **not** post another `bugbot
run` on same SHA. Second trigger without new commit cannot resolve
findings — only duplicates noise. Follow **Fix protocol** end-to-end:
spawn `Task` with `subagent_type: "generalPurpose"` plus clean-coder
**Read** preamble (never ad-hoc shell or bare `generalPurpose` prompt for
production edits), commit and push with pre-commit and pre-push hook
validation (full stop and notify user if hooks bypassed), reply inline on
each thread, then Step 3 `bugbot run` against new SHA.

### Step 4: Loop pacing

**`ScheduleWakeup` field hints** (prefer [Pacing
workflows](#pacing-workflows-load-exactly-one)):

- `delaySeconds: 270` after bugbot re-trigger. Bugbot finishes in 1–4
  min; 270s stays under 5-min prompt-cache TTL with margin. Exception:
  BUGBOT inline-lag branch uses `delaySeconds: 60` (no re-trigger;
  awaiting GitHub inline API).
- `reason`: short sentence on what is awaited, including `phase` and
  `bugbot_clean_at` SHA.
- `prompt: "/pr-converge"` — default. Harness needs `/loop` wrapper →
  `prompt: "/loop /pr-converge"`.

In Step 2 and Fix protocol, "schedule next wakeup, return" means load
pacing workflow, execute Step 4, return.

**Entry paths:** `/pr-converge`, `/loop /pr-converge`, AHK `continue`,
or `ScheduleWakeup` with `prompt` of `/pr-converge` or `/loop
/pr-converge`.

**On convergence:** apply **Convergence** section of same pacing
workflow (omit wakeups / stop AHK).

## Fix protocol

### Cursor `Task` registry (single-PR / Cursor host)

Cursor's `Task` validates `subagent_type` against fixed enum;
`"clean-coder"` not valid. With no `state.json`, **production edits** use
`Task` with `subagent_type: "generalPurpose"` plus clean-coder contract in
`prompt` per **Implement** bullet — not separate `clean-coder` spawn.

Fix protocol runs in `clean-coder` teammate when `state.json` drives
session, or in `Task` + `generalPurpose` in main session when no
`state.json`. Orchestrator **never** performs production edits inline in
multi-PR mode. Pre-commit and pre-push hook handling per §Ground rules and
gates below.

**Multi-PR (`state.json`) teammate obligations** (plus TDD, commit, push):

- Replies inline on each addressed finding via
  `reply_to_inline_comment.py` (what changed + commit identifier),
  matching §Audit result → fix worker step 4 — **before** writing
  `state.json` and going idle.
- Writes `last_action: "fix_pushed"`, `current_head: <new SHA>`,
  `bugbot_clean_at: null`, `phase: "BUGBOT"`, `status: "awaiting_bugbot"`,
  `last_updated` (ISO-8601 UTC) to `state.json` (per §Concurrency).
- Goes idle. Orchestrator spawns follow-up `general-purpose` agent for
  bugbot trigger and monitoring.

Orchestrator does not reply inline, trigger bugbot, or read repo source
files during fix phase in multi-PR mode.

**Single-PR (no `state.json`) — same gates, main session executor:**

- Read each referenced file:line.
- Write failing test first when finding has behavior to test. Pure doc /
  comment / naming nits with no behavior → straight to fix.
- **Implement** by invoking `Task` with `subagent_type: "generalPurpose"`.
  The `prompt` MUST begin by requiring the subagent to **Read** the
  clean-coder agent markdown **before** editing production files: on
  macOS/Linux `$HOME/.claude/agents/clean-coder.md`, on Windows
  `%USERPROFILE%\.claude\agents\clean-coder.md`. The prompt MUST state that
  file is binding for code generation (naming, TDD when behavior changes,
  hook-safe single commit, scope limited to listed findings). Do **not**
  use ad-hoc shell edits for production code. Do **not** emit a bare
  `generalPurpose` prompt that omits the clean-coder Read step. If `Task`
  cannot be invoked, **full stop** and tell the user — do not substitute
  another subagent type for production edits.
- Stage affected files and create one new commit on existing branch:
  ```bash
git add <files> && git commit -m "fix(review): <brief summary>"
  ```
**Pre-commit gate:** Never pass `--no-verify`, `--no-gpg-sign` (unless the user
has explicitly required otherwise), or any flag that skips hooks. After `git
commit`, confirm from the **same terminal transcript** that the **pre-commit**
hook ran (visible hook output or your configured hook runner's success banner)
and exited **0**. If the transcript shows hooks were **skipped**, **bypassed**,
or **did not run** when your repo expects them, **full stop** — do not push, do
not reply inline, do not trigger Bugbot — and notify the user with what you
observed. When a hook **rejects** (non-zero exit), read the message, fix the
cause, retry commit until hooks pass.
- Push the new commit:
  ```bash
git push origin <BRANCH>
  ```
**Pre-push gate:** Never pass `--no-verify` or equivalent. After `git push`,
confirm from the **same terminal transcript** that **pre-push** ran (when your
repo defines a pre-push hook) and exited **0**. If push output shows pre-push
was **skipped**, **bypassed**, or **absent** when it should have run, **full
stop** — do not update `current_head`, do not reply inline, do not trigger
Bugbot — and notify the user. Capture the new HEAD SHA only after both gates
pass. Set `current_head` to it. Set `bugbot_clean_at = null`.
- Reply inline on each addressed comment thread using `--body-file` (per
  gh-body-file rule):
  ```bash
python "${CLAUDE_SKILL_DIR}/scripts/reply_to_inline_comment.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER> \
--comment-id <COMMENT_ID> --body-file <path/to/reply.md>
  ```
- **After pushing a fix, always run Step 3 (`bugbot run`) in the same
  tick** regardless of phase. New commit **resets full convergence cycle**:
  prior bugbot clean and prior second-audit clean on older SHA do **not**
  count toward convergence on new `HEAD`. Must re-obtain bugbot CLEAN on
  `current_head`, then second-audit CLEAN on same `HEAD` with no
  intervening push. Re-triggering in same tick saves a wakeup cycle vs
  deferring Step 3.

## Stop conditions

- **Convergence** (back-to-back clean ∧ no outstanding Copilot findings
  on `current_head` ∧ `mergeStateStatus == "CLEAN"` with `mergeable ==
  "MERGEABLE"` ∧ post-convergence Copilot request resolved — `clean` at
  `current_head`, or `dirty` with follow-up PR opened per §Convergence
  gates (c)): prefer `mark_pr_ready.py`; else `gh pr ready`. With
  `state.json`, append convergence row to
  `<TMPDIR>/pr-converge-<session_id>/converged.log` per `reference/multi-pr-orchestration.md` §Memory; else
  skip. Report §Convergence gates (d) summary, then **omit loop pacing**
  per **Convergence** in pacing workflow (or omit `ScheduleWakeup` when
  no workflow file). End all loops once all PRs converged.
- **Hard blocker:** API auth failure across two ticks, CI regression
  whose root cause falls outside this PR, hook rejection unresolved
  across three commits, `inline_lag_streak >= 3`, **bugteam** reports
  stuck, or post-convergence Copilot request fails to surface review on
  `current_head` after three consecutive wakeups. Report specific
  blocker and diagnosis, **omit loop pacing** per active workflow; stop
  AHK auto-typer per `workflows/ahk-auto-continue-loop.md` **Stop /
  safety** if active.
- **Hard blocker (`mergeStateStatus` non-CLEAN non-DIRTY):**
  `mergeStateStatus` is `BLOCKED`, `UNKNOWN`, or `BEHIND` (required
  checks pending, branch behind base without textual conflicts, or
  GitHub indeterminate). Investigate before retrying; `rebase` skill
  handles `DIRTY` (textual conflicts) only. Report specific
  `mergeStateStatus`, **omit loop pacing**; stop AHK auto-typer per
  `workflows/ahk-auto-continue-loop.md` **Stop / safety** if active.
- **User stops loop:** "stop the converge loop" → **omit loop pacing**
  per active workflow; stop AHK auto-typer per
  `workflows/ahk-auto-continue-loop.md` **Stop / safety** if active.

## Ground rules

- **Append commits.** Each tick adds at most one fix commit. Multiple
  findings collapse into one commit; next tick handles next round.
- **Bugbot findings on current SHA mean fix-then-push-then-`bugbot run`,
  not another naked `bugbot run`.** Unaddressed Bugbot errors require Fix
  protocol before Step 3; `bugbot run` without new commit does not clear
  review state.
- **`bugbot_clean_at` resets on every push.** New commit invalidates
  bugbot's prior clean — bugbot must re-review new HEAD before
  convergence.
- **`copilot_clean_at` and `merge_state_status` reset on every push.**
  Same invalidation for Copilot reviewer's prior clean and `gh pr view`
  mergeability snapshot — both re-check on new HEAD before §Convergence
  gates pass.
- **Convergence requires four gates on same HEAD.** (1) Back-to-back
  clean (Bugbot ∧ **bugteam** with no intervening fixes), (2) no
  outstanding Copilot findings on `current_head`, (3) `mergeStateStatus
  == "CLEAN"` with `mergeable == "MERGEABLE"`, (4) post-convergence
  Copilot request resolved (Copilot clean at HEAD, or follow-up PR
  opened off HEAD capturing Copilot findings). Any gate failing leaves
  PR in-progress.
- **Clean Bugbot on `HEAD` means advance to second audit, not another
  `bugbot run`.** Set `bugbot_clean_at` and run BUGTEAM per Step 2 —
  never post `bugbot run` as substitute.
- **`bugbot run` comment is load-bearing.** Literal phrase `bugbot run`
  exactly — empirically the only re-trigger Cursor Bugbot recognizes.
- **`gh pr ready` / `mark_pr_ready.py` is convergence action.** Mark PR
  ready for review and stop. Merge, reviewers, title, body remain user's
  decisions; skill contract ends at "ready for review."
- **Honor pre-push and pre-commit hooks.** Hook rejects the change → read
  output, fix underlying issue (failing test, missing constant, broken
  import), retry.
- **Adapt when reality contradicts on-disk state.** Spec assumes
  `state.json` (when used) and `git`/`gh` agree with live PR. Divergence
  — user pushed manually between ticks, branch force-reset, worktree
  moved, PR closed/merged externally, `gh` auth dropped mid-tick — **do
  not execute spec literally against stale state**. Report specific drift,
  escalate as hard blocker per §Stop conditions; user decides whether to
  reset loop, refresh credentials, or stop.

## Examples

13 worked examples covering the routine ticks (BUGBOT classify, fix push,
phase transitions) and the edge cases (`mergeStateStatus: DIRTY` rebase,
Copilot `CHANGES_REQUESTED` post-convergence, follow-up PR open) live in
[`reference/examples.md`](reference/examples.md). Read on demand when a
tick is ambiguous against the rules above.
