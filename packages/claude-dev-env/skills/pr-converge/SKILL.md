---
name: pr-converge
description: >-
  Drives the current PR to convergence by alternating Cursor Bugbot and the
  in-house bugteam audit. Each invocation runs one tick of work in the main
  session: fetches the latest reviewer state, applies TDD fixes for any
  findings, pushes one commit per tick, replies inline, and re-triggers the
  reviewer. Default behavior loops until back-to-back clean: pace the next tick
  with ScheduleWakeup when the harness exposes it, otherwise use the AHK
  auto-continue driver (see workflows/ahk-auto-continue-loop.md). Pacing details
  live in workflows next to SKILL.md — load exactly one per Step 4.
  `/loop /pr-converge` is the same loop with an explicit /loop wrapper when the
  harness or habit calls for it — not required for looping.
  Convergence requires a back-to-back clean cycle (bugbot CLEAN immediately
  followed by bugteam CLEAN with no intervening fixes), at which point the PR
  is flipped to ready for review and the loop terminates. Triggers:
  '/pr-converge', '/loop /pr-converge', 'drive PR to convergence', 'loop bugbot and bugteam',
  'babysit bugbot and bugteam', 'until both are clean', 'converge this PR'.
---

# PR Converge

Each **invocation** runs **one tick** of the bugbot ↔ bugteam loop in the **parent session** (fetch state, address findings under the Fix
  protocol when needed, at most one fix commit per tick, inline replies, Bugbot re-trigger rules in Step 2 / Step 3). **By default** the skill
  **keeps going** until back-to-back clean on the same `HEAD`: after each tick, **Step 4** schedules the next tick with `ScheduleWakeup` when
  the tool exists, otherwise uses the **AHK auto-continue** driver. On convergence, run `gh pr ready`, then **stop all pacing** (omit further
  `ScheduleWakeup`; stop the AHK auto-typer when that fallback was in use).

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

This skill **complements** **`/bugteam`**: it sequences Bugbot re-reviews, **`/bugteam`** runs, the Fix protocol, and inline replies between
  pushes until back-to-back clean. The in-house audit on every BUGTEAM tick is **`/bugteam`** (bugteam skill), not a parallel substitute. **Fix
  protocol** code changes use **`Task` + `clean-coder`** per project agent files. **Loop pacing** stays in the **main** session.

## Pacing workflows (load exactly one)

Before **Step 4** on each tick, decide whether **`ScheduleWakeup` is invokable** in this session (orchestrated teams / tool registry).
  **Use the Read tool** on exactly one file under the same directory as this skill's `SKILL.md` (installed copies usually live under
  `$HOME/.claude/skills/pr-converge/`):

| Route | Read this file |
| --- | --- |
| `ScheduleWakeup` available | `workflows/schedule-wakeup-loop.md` |
| `ScheduleWakeup` not available | `workflows/ahk-auto-continue-loop.md` |

All pacing-specific instructions for that route — delays, prompts, AHK setup, `continue` handling, convergence cleanup for the auto-typer,
  inline-lag pacing split, and route-only gotchas — live **only** in that workflow file. This `SKILL.md` keeps shared bugbot / bugteam / Fix
  protocol / stop rules.

- **`/pr-converge`** (default): loops until convergence. After each tick (unless converged or stopped), run **Step 4**, which starts by loading
  the correct workflow row from the table above.

## State across ticks

Unless the harness stores the same fields elsewhere, track the following **in each assistant turn as plain text** so the **next tick that
  resumes in this transcript** can re-read them from conversation context:

- `phase`: `BUGBOT` or `BUGTEAM`. Start in `BUGBOT` on the first tick of a fresh loop.
- `bugbot_clean_at`: the HEAD SHA at which bugbot last reported clean, or `null`. Reset to `null` whenever a new commit is pushed.
- `inline_lag_streak`: integer counter, initialized to `0`. Tracks consecutive ticks where bugbot's review body indicates findings against
  `current_head` but the inline-comments API returns zero matching comments. Reset to `0` on any other branch outcome.
- `tick_count`: integer, initialized to `0`. Increment on every tick to enforce the safety cap.

Each tick begins by reading the prior tick's state line from the most recent assistant message and ends by emitting the updated state line.

## Per-tick work

### Step 1: Resolve current HEAD and PR context

Read the prior tick's state line from the most recent assistant message (or initialize all fields if none). **Increment `tick_count` by 1.**
  This is the increment referenced in the **State across ticks** section; without it the safety cap (Step 3.5, §Safety cap) never fires.

```bash
gh pr view --json number,url,headRefOid,baseRefName,headRefName,isDraft
```

Capture `number` (`<NUMBER>`), `headRefOid` (`current_head`), owner/repo (from `url`), branch name (`<BRANCH>`).

### Step 2: Branch on `phase`

#### `phase == BUGBOT`

a. Fetch Cursor Bugbot reviews newest-first and walk backwards until the first clean review:

   ```bash
   gh api repos/<OWNER>/<REPO>/pulls/<NUMBER>/reviews \
     --jq '[.[] | select(.user.login=="cursor[bot]")] | sort_by(.submitted_at) | reverse'
   ```

   Track dirty reviews in a temp file as you walk; the Fix protocol reads it back later in this tick:

   ```bash
   dirty_reviews_path=$(mktemp "${TMPDIR:-/tmp}/pr-converge-bugbot.XXXXXX")
   : > "$dirty_reviews_path"
   ```

   Iterate from index 0 (most recent) toward older entries:

   - Classify each review's body — **dirty** when it contains `Cursor Bugbot has reviewed your changes and found <N> potential issue`;
     **clean** otherwise.
   - For a dirty review, append one JSON line to `$dirty_reviews_path` with `{review_id, commit_id, submitted_at, body}`.
   - Stop at the first clean review. Older reviews are presumed addressed at that clean checkpoint and are not re-read.
   - When index 0 is itself clean, `$dirty_reviews_path` stays empty.

   Capture `commit_id`, `state`, `submitted_at`, and body of the index-0 review for the decision branches below. When a branch routes to the
     **Fix protocol**, read every entry from `$dirty_reviews_path` and address all of them — not just index 0.

b. Fetch unaddressed inline comments from `cursor[bot]` on `current_head`:
   ```bash
   gh api repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments \
     --jq "[.[] | select(.user.login==\"cursor[bot]\") | select(.commit_id==\"$current_head\")]"
   ```

c. Decide (the four branches below cover every input combination — match the first branch whose predicate holds):
   - **No bugbot review yet, OR latest bugbot review's `commit_id` differs from `current_head`:** Re-trigger bugbot (Step 3), set
     `bugbot_clean_at = null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND zero unaddressed inline findings AND review body indicates clean:** Set `bugbot_clean_at
     = current_head`. Reset `inline_lag_streak = 0`. Transition `phase = BUGTEAM`. Continue to bugteam branch in this same tick — back-to-back
     convergence requires bugteam to run against the same HEAD before the next wakeup is scheduled.
   - **Latest review's `commit_id == current_head` with unaddressed inline findings (review body indicates findings):** Apply the **Fix
     protocol** below to address them. Reset `inline_lag_streak = 0`. The fix protocol pushes a new commit, which sets `current_head` to the
     new SHA, sets `bugbot_clean_at = null`, replies inline on each thread, and re-triggers bugbot. Schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND review body indicates findings AND inline-comments API returns zero matching comments
     for `current_head`:** Treat as transient API propagation lag — bugbot publishes the review body and inline comments through separate API
     operations and the two writes can briefly desync. Increment `inline_lag_streak`. When `inline_lag_streak >= 3`, escalate as a hard blocker
     (bugbot review is structurally inconsistent — body claims findings while inline anchors stay empty across three consecutive ticks); report
     and terminate with no loop pacing; stop the AHK auto-typer per `workflows/ahk-auto-continue-loop.md` if that pacing path was active.
     Otherwise complete **Step 4** using the **BUGBOT inline-lag** section of the pacing workflow file you already chose for this session (see
     table under [Pacing workflows](#pacing-workflows-load-exactly-one)). The inline comments should appear on the next tick.

**Gotcha (Bugbot already clean on `HEAD`, but another `bugbot run` fires):** When the latest Bugbot review on `current_head` already indicates
  **clean / no issues** (the branch above that sets `bugbot_clean_at` and transitions to **`phase = BUGTEAM`**), the next action must be the
  **BUGTEAM audit in the same tick**. Invoke **`/bugteam`** via the `Skill` tool using the fenced invocation in
  Step 2 below. If merged findings require commits, continue with **Fix protocol** using **`clean-coder`**. If clean coder is not available, 
  STOP and notify the user. Posting `bugbot run` again after a clean review skips the mandated bugteam pass.

#### `phase == BUGTEAM`

a. Run the **`/bugteam`** audit on the PR(s) from this session. Invoke the `Skill` tool:

     ```
     Skill({skill: "bugteam", args: "https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"})
     ```

     **Orchestrated teams available:** the main session may act as team lead and `TeamCreate` may run from the orchestrator alongside `/bugteam`
     teammate spawn lines and audit progress.
     **No team / orchestration compatibility:** `/bugteam` still runs via `Skill` — expect CODE_RULES gate output and audit progress, but do **not**
     assume `TeamCreate` or teammate spawn lines. In both cases the skill audits the PR against CODE_RULES, posts review threads, and converges
     or stops at its own internal cap. Wait for completion; capture exit and final summary.

b. **Re-resolve current HEAD now** because `/bugteam` may have pushed commits during its run. The `current_head` from Step 1 is potentially
  stale at this point:
   ```bash
   new_head=$(gh api repos/<OWNER>/<REPO>/pulls/<NUMBER> --jq '.head.sha')
   ```
   If `new_head != current_head`, set `current_head = new_head` AND set `bugbot_clean_at = null`. The new commits from bugteam invalidate
     bugbot's prior clean.

c. Inspect bugteam's output. Bugteam reports either `convergence (zero findings)` or a list of unfixed findings with file:line.

d. Decide based on the (post-bugteam) state — order matters; check pushed-during-bugteam FIRST so a convergence report against a stale HEAD
  never falsely terminates:
   - **bugteam pushed during this tick (i.e., `bugbot_clean_at` was just reset to `null` in step b):** Re-trigger bugbot in this same tick
     (Step 3) so the new HEAD enters bugbot's queue immediately, transition `phase = BUGBOT`, schedule next wakeup, return. The new commit
     needs a fresh bugbot review before convergence can be claimed.
   - **bugteam reports convergence AND `bugbot_clean_at == current_head` (no push during this tick):** This is back-to-back clean. Mark the PR
     ready for review:
     ```bash
     gh pr ready <NUMBER> --repo <OWNER>/<REPO>
     ```
     Report one sentence to the user: "PR #<NUMBER> converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for review."
     **Omit loop pacing** per the **Convergence** section of whichever pacing workflow was active (`workflows/schedule-wakeup-loop.md` or
     `workflows/ahk-auto-continue-loop.md`).
   - **bugteam reports convergence BUT `bugbot_clean_at != current_head` (no push during this tick):** Bugteam reached zero findings without
     committing, yet bugbot still needs re-confirmation against this HEAD. This branch is reachable only when state diverged BETWEEN ticks —
     for example, the user pushed a manual commit between two wakeups, leaving `current_head` ahead of the SHA bugbot last cleaned. Transition
     `phase = BUGBOT`, schedule next wakeup, return.
   - **bugteam reports findings without committing fixes:** apply the **Fix protocol** below (which always re-triggers bugbot after the push),
     transition `phase = BUGBOT`, schedule next wakeup, return.

### Step 3: Re-trigger bugbot

Used in Step 2 BUGBOT branch 1, in Step 2 BUGTEAM branch 1, and in the Fix protocol. Post a literal `bugbot run` PR comment. Prefer the bundled
  script (writes the body to a temp file and calls `gh` with `--body-file` internally, satisfying the gh-body-file rule):

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" "https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"
```

Shorthand `owner/repo#number`:

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" "<OWNER>/<REPO>#<NUMBER>"
```

Explicit number when `gh` already has a default repo (optional):

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" -Repository "<OWNER>/<REPO>" -Number <NUMBER>
```

If you cannot run the script, use the Write tool to a temp file, then `gh pr comment <NUMBER> --repo <OWNER>/<REPO> --body-file <path>` yourself.
  The body file must contain exactly the literal phrase `bugbot run` followed by a newline — empirically the only re-trigger Cursor Bugbot
  recognizes; alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

**Gotcha (duplicate `bugbot run` while a review is already queued):** Do not post another `bugbot run` when Bugbot has already picked up the
  latest trigger. On GitHub, the signal is an **eyes** (`:eyes:`) reaction on the **most recent** `bugbot run` PR comment (Bugbot acknowledging
  the job). When that reaction is present, skip Step 3 for this wait cycle - a second comment spams the PR and can confuse tick logic; wait for
  the review to finish or for `HEAD` to change before re-triggering per Step 2.

**Gotcha (Bugbot found errors, but a redundant `bugbot run` instead of a fix push):** When the latest Bugbot review on `current_head` still has
  **unaddressed findings** (inline threads and/or a non-clean review body), **do not** post another `bugbot run` on that same SHA as a
  substitute for fixing the code. A second trigger without a new commit cannot resolve the findings — it only duplicates noise and breaks tick
  expectations. Follow the **Fix protocol** end-to-end: spawn **`Task`** with **`subagent_type: "clean-coder"`** (never `generalPurpose` for
  production edits), **commit and push** with mandatory pre-commit and pre-push hook validation (full stop and notify the user if hooks did not
  run or were bypassed), reply inline on each thread, **then** Step 3 `bugbot run` against the new SHA.

### Step 4: Loop pacing

Throughout Step 2 and the Fix protocol, **schedule next wakeup, return** means: load the correct pacing workflow (see
  [Pacing workflows](#pacing-workflows-load-exactly-one)), then execute **Step 4** exactly as that file specifies (pace the next tick, then
  return).

**Entry paths** include `/pr-converge`, an AHK `continue` tick, or a `ScheduleWakeup` whose `prompt` is `/pr-converge`.

**On convergence:** apply the **Convergence** section of the **same** pacing workflow file you are using for this session (omit wakeups / stop
  AHK per that file).

## Fix protocol

Used by both phases when findings exist:

- Read each referenced file:line.
- Write a failing test first when the finding has behavior to test. For pure doc, comment, or naming nits with no behavior, go straight to the
  fix.
- **Implement** by invoking **`Task`** with **`subagent_type: "clean-coder"`** (and the same model or harness your repo documents for that
  agent). If `clean-coder` is unavailable, **full stop** and tell the user.
- Stage the affected files and create one new commit on the existing branch:
  ```bash
  git add <files> && git commit -m "fix(review): <brief summary>"
  ```
  **Pre-commit gate:** Never pass `--no-verify`, `--no-gpg-sign` (unless the user has explicitly required otherwise), or any flag that skips
  hooks. After `git commit`, confirm from the **same terminal transcript** that the **pre-commit** hook ran (visible hook output or your
  configured hook runner’s success banner) and exited **0**. If the transcript shows hooks were **skipped**, **bypassed**, or **did not run**
  when your repo expects them, **full stop** — do not push, do not reply inline, do not trigger Bugbot — and notify the user with what you
  observed. When a hook **rejects** (non-zero exit), read the message, fix the cause, retry commit until hooks pass.
- Push the new commit:
  ```bash
  git push origin <BRANCH>
  ```
  **Pre-push gate:** Never pass `--no-verify` or equivalent. After `git push`, confirm from the **same terminal transcript** that **pre-push**
  ran (when your repo defines a pre-push hook) and exited **0**. If push output shows pre-push was **skipped**, **bypassed**, or **absent** when
  it should have run, **full stop** — do not update `current_head`, do not reply inline, do not trigger Bugbot — and notify the user. Capture
  the new HEAD SHA only after both gates pass. Set `current_head` to it. Set `bugbot_clean_at = null`.
- Reply inline on each addressed comment thread using `--body-file` (per gh-body-file rule):
  ```bash
  gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments/<comment_id>/replies \
    --field body=@<path/to/reply.md>
  ```
- **After pushing a fix, always run Step 3 (`bugbot run`) in the same tick** when you would otherwise wait for Bugbot — regardless of which phase
  originated the findings. Step 3 is the **mechanism** that restarts Bugbot on the new `HEAD`, but the **meaning** is broader: a new commit
  **resets the full convergence cycle**. Prior bugbot clean and prior bugteam clean on an older SHA **do not** count toward convergence on the new
  `HEAD`. You must **again** obtain **bugbot CLEAN** on `current_head`, then **`/bugteam` CLEAN** on that same `HEAD` with **no intervening push**
  (the same back-to-back rule as Step 2). Re-triggering Bugbot in the same tick after the push saves a full wakeup cycle compared to deferring
  Step 3 to the next tick.

## Stop conditions

- **Convergence** (back-to-back clean as defined in Step 2 BUGTEAM second branch — bugteam reports convergence and
  `bugbot_clean_at == current_head` with no push during this tick):
  run `gh pr ready`, report one-sentence summary, then **omit loop pacing** per **Convergence** in the pacing workflow from the Step 4 table. 
  End any ongoing loops once all PRs are converged.
- **Hard blocker:** API auth failure persists across two ticks, a CI regression whose root cause falls outside this PR, a hook rejection
  investigated through three commits and still unresolved, `inline_lag_streak >= 3`, or `/bugteam` itself reports a stuck state. Report the
  specific blocker and the diagnosis, then **omit loop pacing** per the active workflow; stop the AHK auto-typer per
  `workflows/ahk-auto-continue-loop.md` **Stop / safety** if that path was in use.
- **User stops the loop:** user says "stop the converge loop" → **omit loop pacing** per the active workflow; stop the AHK auto-typer per
  `workflows/ahk-auto-continue-loop.md` **Stop / safety** if that path was in use.
- **Safety cap:** `tick_count >= 30` (evaluated in Step 3.5) → **omit loop pacing** per the active workflow; stop the AHK auto-typer per
  `workflows/ahk-auto-continue-loop.md` **Stop / safety** if that path was in use; report the cap was hit. See §Safety cap below for rationale.
## Ground rules

- **Append commits.** Each tick adds at most one new fix commit. Multiple findings within one tick collapse into a single commit; the next tick
  handles the next round.
- **Bugbot findings on the current SHA mean fix-then-push-then-`bugbot run`, not another naked `bugbot run`.** Unaddressed Bugbot errors
  require the Fix protocol (implement, push, inline replies) before Step 3; posting `bugbot run` again without a new commit does not clear the
  review state.
- **`bugbot_clean_at` resets on every push.** A new commit invalidates bugbot's prior clean by definition — bugbot must re-review the new HEAD
  before convergence can be claimed.
- **Back-to-back clean is the ONLY termination criterion.** Convergence requires both reviewers clean against the same HEAD with no intervening
  fixes; either reviewer clean alone counts as in-progress.
- **Clean Bugbot on `HEAD` means advance to bugteam, not another `bugbot run`.** After Bugbot reports clean on the current SHA, the
  orchestrator must set `bugbot_clean_at` and run the **BUGTEAM** audit per Step 2 — never post `bugbot run` as a substitute. That audit is
  **`/bugteam`** via the bugteam skill every time, not a second Bugbot trigger.
- **The `bugbot run` comment is load-bearing.** Use the literal phrase `bugbot run` exactly — empirically the only re-trigger Cursor Bugbot
  recognizes; alternative phrasings silently no-op.
- **`gh pr ready` is the convergence action.** Mark the PR ready for review and stop there. Bugteam's own review output is the in-house audit
  trail on GitHub. Merge, additional reviewers, title, and body remain the user's decisions; the skill's contract ends at "ready for review."
- **Honor pre-push and pre-commit hooks.** When a hook rejects the change, read its output, fix the underlying issue (the failing test, the
  missing constant, the broken import), and retry.

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
