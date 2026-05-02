---
name: pr-converge
description: >-
  Drives the current PR to convergence by alternating Cursor Bugbot and the
  in-house bugteam audit. Each invocation runs one tick of work in the main
  session: fetches the latest reviewer state, applies TDD fixes for any
  findings, pushes one commit per tick, replies inline, and re-triggers the
  reviewer. Default behavior loops until back-to-back clean: pace the next tick
  with ScheduleWakeup when the harness exposes it, otherwise use the AHK
  auto-continue driver (see §Alternative loop driver in the Table of Contents).
  `/loop /pr-converge` is the same loop with an explicit /loop wrapper when the
  harness or habit calls for it — not required for looping. Opt out of looping
  with `/pr-converge once` for a single tick.
  Convergence requires a back-to-back clean cycle (bugbot CLEAN immediately
  followed by bugteam CLEAN with no intervening fixes), at which point the PR
  is flipped to ready for review and the loop terminates. Triggers:
  '/pr-converge', '/pr-converge once', '/loop /pr-converge', 'drive PR to convergence', 'loop bugbot and bugteam',
  'babysit bugbot and bugteam', 'until both are clean', 'converge this PR'.
---

# PR Converge

Runs one tick of the bugbot ↔ bugteam convergence loop in the main session. **Default:** keep looping until convergence (back-to-back clean) — the next tick is paced by `ScheduleWakeup` when available, otherwise by the AHK auto-continue driver. Self-terminates on convergence by flipping the PR to ready for review and omitting further pacing (no `ScheduleWakeup`, stop AHK when that path was used).

## Table of contents

1. [Why the work runs in the main session, not a background subagent](#why-the-work-runs-in-the-main-session-not-a-background-subagent)
2. [When this skill applies](#when-this-skill-applies)
3. [Invocation modes](#invocation-modes)
4. [Alternative loop driver: AHK auto-continue](#alternative-loop-driver-ahk-auto-continue) — default pacing when `ScheduleWakeup` is not callable (still applies when the user prefers AHK over wakeups)
   - [One-time setup at the start of the loop](#one-time-setup-at-the-start-of-the-loop)
   - [Per-tick behavior under this driver](#per-tick-behavior-under-this-driver)
   - [Convergence cleanup](#convergence-cleanup)
   - [Gotchas](#gotchas)
5. [State across ticks](#state-across-ticks)
6. [Per-tick work](#per-tick-work)
   - [Step 1: Resolve current HEAD and PR context](#step-1-resolve-current-head-and-pr-context)
   - [Step 2: Branch on `phase`](#step-2-branch-on-phase)
   - [Step 3: Re-trigger bugbot](#step-3-re-trigger-bugbot)
   - [Step 3.5: Enforce the safety cap](#step-35-enforce-the-safety-cap)
   - [Step 4: Loop pacing (`ScheduleWakeup` or AHK fallback)](#step-4-loop-pacing-schedulewakeup-or-ahk-fallback)
7. [Fix protocol](#fix-protocol)
8. [Stop conditions](#stop-conditions)
9. [Safety cap](#safety-cap)
10. [Ground rules](#ground-rules)
11. [Examples](#examples)

## Why the work runs in the main session, not a background subagent

Run **every converge tick** in the **parent harness session** (the conversation where the user invoked `/pr-converge` or `/loop /pr-converge`):

- **`ScheduleWakeup` path:** Call `ScheduleWakeup` from this same session so the next tick fires back into **this** transcript with the prior tick’s state line and PR context still addressable.
- **AHK path:** Keep ticks in the **same** window the auto-typer targets so each `continue` re-enters here and reads the same state line and `gh` context.

Delegate **audits and fixes** to background `Task` / subagents **only** where this skill already specifies that pattern (for example read-only audit or fix-protocol workers). **Loop pacing** (`ScheduleWakeup` scheduling or AHK handoff) stays in the **main** session.

## When this skill applies

The user is on a PR branch and wants both reviewers — Cursor's Bugbot AND the in-house `/bugteam` audit — to keep re-reviewing after each push, with findings auto-addressed between ticks. The PR stays in draft until convergence; on convergence the skill flips it to ready for review.

## Invocation modes

- **`/pr-converge`** (default): loops until convergence. After each tick (unless converged or stopped), run **Step 4** — prefer `ScheduleWakeup` when the tool is available; otherwise start or rely on the **AHK auto-continue** driver below so the next tick still fires without the user having to remember `/loop`.
- **`/loop /pr-converge`**: equivalent loop semantics when the user prefers an explicit `/loop` wrapper; same Step 4 fork (`ScheduleWakeup` vs AHK) applies.
- **`/pr-converge once`**: opt-in **single tick** only — skips Step 4 pacing entirely (no `ScheduleWakeup`, no AHK setup for continuation). Use for ad-hoc inspection or advancing one step by hand.

## Alternative loop driver: AHK auto-continue

Use this as the **default pacing path** whenever `ScheduleWakeup` is not callable in this session (orchestrated teams disabled, restricted tool registry, Cursor without that primitive, or the user wants a visibly-running pacer). It is not a separate "mode" the user must remember — bare `/pr-converge` already implies loop-until-done; when the primary wakeup tool is missing, fall through to AHK automatically. The per-tick work is unchanged; what changes is who fires the next tick. Instead of `ScheduleWakeup` re-entering the skill, an external AutoHotkey utility auto-types `continue` into the active Claude Code window every 5 minutes, and the model treats each `continue` as the next tick trigger. The same **alternative-mode** harness constraint applies to **BUGTEAM** (see Step 2 `phase == BUGTEAM` and **Gotchas** below): there is no `Skill({skill: "bugteam"})` in this session — substitute the **read-only audit** with **parallel `Task` + `code-quality-agent`** (`readonly: true`), never `generalPurpose`. Treat merged output as the bugteam audit verdict; **implementation** and **Fix protocol** commits use **`Task` + `clean-coder`** only. If `.cursor/agents/code-quality-agent.md` or `.cursor/agents/clean-coder.md` is missing, copy from `~/.claude/agents/` into `.cursor/agents/` before spawning.

### One-time setup at the start of the loop

The skill bundles its driver scripts under `scripts/` and resolves them at runtime via `$HOME\.claude\skills\pr-converge\scripts\…` (the same convention `/logifix` uses). The bundled `.cmd` launchers locate their siblings via `%~dp0`, so they need no path arguments — only the AHK target PID.

Run these two commands in order (PowerShell-friendly Bash escaping):

1. Resolve the PID of the GUI ancestor that hosts this Claude Code session:
   ```bash
   pwsh -NoProfile -ExecutionPolicy Bypass -File "$HOME\.claude\skills\pr-converge\scripts\caller-window-pid.ps1"
   ```
   Capture the printed integer as `caller_pid`. Verify it points at the right window before continuing:
   ```bash
   pwsh -NoProfile -Command "Get-Process -Id $caller_pid | Select-Object Id,ProcessName,MainWindowTitle"
   ```
2. Launch the auto-typer attached to that PID with auto-start enabled. The bundled launcher accepts the PID as its first arg and the `--start-on` flag is forwarded to the AHK script:
   ```bash
   "$HOME\.claude\skills\pr-converge\scripts\cursor-agents-continue.cmd" $caller_pid --start-on
   ```
   AutoHotkey v2 must be installed at `C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe`.

### Per-tick behavior under this driver

- Run Steps 1–3 of **Per-tick work** exactly as written.
- In **Step 4**, do **not** call `ScheduleWakeup` — the auto-typer is the pacer (this is the fallback branch of Step 4).
- End every assistant response with the literal sentence `Awaiting next "continue" tick.` so the next iteration is unambiguously identifiable in the transcript.
- When the next user message is `continue` (auto-typed by AHK) or any close paraphrase, treat it as the next tick of default-loop `/pr-converge` and re-enter from Step 1 against the freshest PR state.

### Convergence cleanup

On back-to-back clean (the existing convergence rule), ensure the **BUGTEAM substitute audit** is already posted as a **`gh pr comment --body-file`** on the PR **before** `gh pr ready` when using [alternative mode](#alternative-loop-driver-ahk-auto-continue) — then run `gh pr ready`, then kill the auto-typer:

```bash
pwsh -NoProfile -Command "Get-Process AutoHotkey64 -ErrorAction SilentlyContinue | Stop-Process -Force"
```

Report convergence in the same one-sentence shape as the standard flow, plus a second sentence noting the auto-typer was stopped. The skill returns; no next tick fires.

### Gotchas

- **Resolver fallback semantics matter.** `caller-window-pid.ps1` walks up the parent process chain, terminates at `explorer.exe`, and falls back to the foreground window when no GUI ancestor is found. Always verify `MainWindowTitle` after capture — if it isn't the Claude Code session, the auto-typer will fire `continue` into the wrong window and the loop stalls silently.
- **Tick-duration vs. 5-minute cadence.** The auto-typer fires every 5 minutes regardless of model activity. A tick that runs longer than 5 minutes will receive a queued `continue` while still in flight; Claude Code processes these sequentially, so there's no corruption, but the loop pace becomes irregular. Don't try to "fix" this by shortening the AHK interval — the `bugbot run` cadence already has its own pacing baked into the standard flow.
- **AHK runs as `#SingleInstance Force`.** Re-running the launcher replaces the prior instance silently. Safe to re-issue if the loop appears stalled.
- **`Stop-Process -Force` on `AutoHotkey64` is broad.** It kills every AHK instance, not just the one this skill started. When the user has unrelated AHK utilities running, scope the kill by command-line match instead:
  ```bash
  pwsh -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='AutoHotkey64.exe'\" | Where-Object CommandLine -like '*cursor-agents-continue.ahk*' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
  ```
- **State-line responsibility is unchanged.** The state line (phase, bugbot_clean_at, inline_lag_streak, tick_count) is still emitted at the end of every tick — it's how the next tick reads prior state. The auto-typer only fires `continue`; it does not preserve state for you.
- **Safety cap still applies.** `tick_count >= 30` terminates the loop and kills the auto-typer in this mode just as it omits `ScheduleWakeup` in primary pacing mode. The structural-failure interpretation is the same.
- **BUGTEAM runs in-session, not via `Skill({skill: "bugteam"})`.** Alternative mode means Claude Code orchestration (including `TeamCreate` and the `bugteam` skill) is out of scope. After Bugbot is clean on `current_head`, the BUGTEAM **audit** must be satisfied by spawning **parallel background `Task` + `code-quality-agent`** runs (`readonly: true`) in **this** Cursor assistant session, awaiting every completion, then merging into one verdict for Step 2 branches b–d. Waiting on a `Skill` tool that the harness cannot invoke stalls the loop.
- **Cursor: `code-quality-agent` for read-only audit; `clean-coder` for code changes.** Parallel PR/diff **audits** (including the BUGTEAM substitute and multi-PR status ticks) use `Task` with `subagent_type: "code-quality-agent"` and `readonly: true`. **Fix protocol** and any commit that changes production code use `Task` with `subagent_type: "clean-coder"`. Do **not** use `generalPurpose` for audit or fix work — wrong tool class. Ensure `.cursor/agents/code-quality-agent.md` and `.cursor/agents/clean-coder.md` exist; copy from `~/.claude/agents/` when missing.
- **BUGTEAM substitute must leave a PR comment before `gh pr ready`.** In alternative mode, the merged `code-quality-agent` verdict exists only in chat until you **`gh pr comment --body-file`** it. Skipping that step means the PR shows Bugbot clean + ready flip with **no** in-house audit mirror — a converge gotcha.

## State across ticks

Track the following in plain text in the assistant's response so subsequent ticks can re-read it from conversation context:

- `phase`: `BUGBOT` or `BUGTEAM`. Start in `BUGBOT` on the first tick of a fresh loop.
- `bugbot_clean_at`: the HEAD SHA at which bugbot last reported clean, or `null`. Reset to `null` whenever a new commit is pushed.
- `inline_lag_streak`: integer counter, initialized to `0`. Tracks consecutive ticks where bugbot's review body indicates findings against `current_head` but the inline-comments API returns zero matching comments. Reset to `0` on any other branch outcome.
- `tick_count`: integer, initialized to `0`. Increment on every tick to enforce the safety cap.

Each tick begins by reading the prior tick's state line from the most recent assistant message and ends by emitting the updated state line.

## Per-tick work

### Step 1: Resolve current HEAD and PR context

Read the prior tick's state line from the most recent assistant message (or initialize all fields if none). **Increment `tick_count` by 1.** This is the increment referenced in the **State across ticks** section; without it the safety cap (Step 3.5, §Safety cap) never fires.

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

   - Classify each review's body — **dirty** when it contains `Cursor Bugbot has reviewed your changes and found <N> potential issue`; **clean** otherwise.
   - For a dirty review, append one JSON line to `$dirty_reviews_path` with `{review_id, commit_id, submitted_at, body}`.
   - Stop at the first clean review. Older reviews are presumed addressed at that clean checkpoint and are not re-read.
   - When index 0 is itself clean, `$dirty_reviews_path` stays empty.

   Capture `commit_id`, `state`, `submitted_at`, and body of the index-0 review for the decision branches below. When a branch routes to the **Fix protocol**, read every entry from `$dirty_reviews_path` and address all of them — not just index 0.

b. Fetch unaddressed inline comments from `cursor[bot]` on `current_head`:
   ```bash
   gh api repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments \
     --jq "[.[] | select(.user.login==\"cursor[bot]\") | select(.commit_id==\"$current_head\")]"
   ```

c. Decide (the four branches below cover every input combination — match the first branch whose predicate holds):
   - **No bugbot review yet, OR latest bugbot review's `commit_id` differs from `current_head`:** Re-trigger bugbot (Step 3), set `bugbot_clean_at = null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND zero unaddressed inline findings AND review body indicates clean:** Set `bugbot_clean_at = current_head`. Reset `inline_lag_streak = 0`. Transition `phase = BUGTEAM`. Continue to bugteam branch in this same tick — back-to-back convergence requires bugteam to run against the same HEAD before the next wakeup is scheduled.
   - **Latest review's `commit_id == current_head` with unaddressed inline findings (review body indicates findings):** Apply the **Fix protocol** below to address them. Reset `inline_lag_streak = 0`. The fix protocol pushes a new commit, which sets `current_head` to the new SHA, sets `bugbot_clean_at = null`, replies inline on each thread, and re-triggers bugbot. Schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND review body indicates findings AND inline-comments API returns zero matching comments for `current_head`:** Treat as transient API propagation lag — bugbot publishes the review body and inline comments through separate API operations and the two writes can briefly desync. Increment `inline_lag_streak`. When `inline_lag_streak >= 3`, escalate as a hard blocker (bugbot review is structurally inconsistent — body claims findings while inline anchors stay empty across three consecutive ticks); report and terminate with no loop pacing; stop the AHK auto-typer if it was started. Otherwise complete Step 4 in loop mode and return: in the `ScheduleWakeup` branch use `delaySeconds: 60` (lag is short-lived); in the AHK branch of Step 4, end per **Per-tick behavior under this driver** (fixed AHK cadence — there is no 60s shortcut). The inline comments should appear on the next tick.

**Gotcha (Bugbot already clean on `HEAD`, but another `bugbot run` fires):** When the latest Bugbot review on `current_head` already indicates **clean / no issues** (the branch above that sets `bugbot_clean_at` and transitions to **`phase = BUGTEAM`**), the next action must be the **BUGTEAM audit in the same tick** — **not** another `bugbot run`. In **Claude Code**, that is **`/bugteam`** via `Skill({skill: "bugteam", ...})` when the tool exists. In **alternative mode** (AHK driver / Cursor session without that skill), run **parallel background `Task` + `code-quality-agent`** (`readonly: true`) against the PR as the bugteam **audit** substitute (not `generalPurpose`). If merged findings require commits, continue with **Fix protocol** using **`clean-coder`**. Posting `bugbot run` again after a clean review skips the mandated bugteam pass.

#### `phase == BUGTEAM`

a. Run the in-house bugteam audit on the current PR — **pick the harness that matches the session:**

   - **Claude Code (standard):** invoke the `Skill` tool in the main session:

     ```
     Skill({skill: "bugteam", args: "https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"})
     ```

     The main session is the team lead, so `TeamCreate` fires from the orchestrator and `/bugteam` emits its CODE_RULES gate output, teammate spawn lines, and audit progress as expected. The skill audits the current PR against CODE_RULES, posts review threads, and converges or stops at its own internal cap. Wait for it to complete; capture exit and final summary.

   - **Alternative mode** (same constraints as [Alternative loop driver: AHK auto-continue](#alternative-loop-driver-ahk-auto-continue) — no `bugteam` skill / no `TeamCreate` in this session): spawn **parallel background `Task` runs with `subagent_type: "code-quality-agent"`** and **`readonly: true`** (confirm `.cursor/agents/code-quality-agent.md` exists — copy from `~/.claude/agents/code-quality-agent.md` if missing) against the current PR scope (full diff or project-defined slices), await every completion, then merge into one **read-only audit** summary equivalent to bugteam output (convergence with zero findings vs list of file:line findings). **Persist that merged verdict on GitHub** before any convergence `gh pr ready`: `gh pr comment <NUMBER> --repo <OWNER>/<REPO> --body-file <path/to/bugteam_substitute_audit.md>` where the body names `current_head`, P0/P1/P2 counts, and convergence YES/NO (per gh-body-file rule). In-session transcript alone is **not** sufficient — reviewers must see the audit on the PR timeline. Do **not** substitute `generalPurpose` for audit work. If the audit implies code fixes, run **Fix protocol** with **`clean-coder`** (not `code-quality-agent`). Use the merged audit summary for steps b–d below. Do not invoke `Skill({skill: "bugteam"})` when the harness cannot satisfy it.

b. **Re-resolve current HEAD now** because `/bugteam` may have pushed commits during its run. The `current_head` from Step 1 is potentially stale at this point:
   ```bash
   new_head=$(gh api repos/<OWNER>/<REPO>/pulls/<NUMBER> --jq '.head.sha')
   ```
   If `new_head != current_head`, set `current_head = new_head` AND set `bugbot_clean_at = null`. The new commits from bugteam invalidate bugbot's prior clean.

c. Inspect bugteam's output. Bugteam reports either `convergence (zero findings)` or a list of unfixed findings with file:line.

d. Decide based on the (post-bugteam) state — order matters; check pushed-during-bugteam FIRST so a convergence report against a stale HEAD never falsely terminates:
   - **bugteam pushed during this tick (i.e., `bugbot_clean_at` was just reset to `null` in step b):** Re-trigger bugbot in this same tick (Step 3) so the new HEAD enters bugbot's queue immediately, transition `phase = BUGBOT`, schedule next wakeup, return. The new commit needs a fresh bugbot review before convergence can be claimed.
   - **bugteam reports convergence AND `bugbot_clean_at == current_head` (no push during this tick):** This is back-to-back clean. In **alternative mode**, post the **BUGTEAM substitute audit digest** to the PR first (`gh pr comment … --body-file`, same fields as Step 2 alternative branch — **never** skip this: without it, `gh pr ready` leaves no auditor paper trail on GitHub). Then mark the PR ready for review:
     ```bash
     gh pr comment <NUMBER> --repo <OWNER>/<REPO> --body-file <path/to/bugteam_substitute_audit.md>
     gh pr ready <NUMBER> --repo <OWNER>/<REPO>
     ```
     In **Claude Code** (`/bugteam` via `Skill`), the skill's review threads already create GitHub-visible output — the `gh pr comment` audit digest step is **alternative mode only**. Report to the user in one sentence: "PR #<NUMBER> converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for review." **Omit loop pacing** — no `ScheduleWakeup`; stop the AHK auto-typer if this session used the fallback driver.
   - **bugteam reports convergence BUT `bugbot_clean_at != current_head` (no push during this tick):** Bugteam reached zero findings without committing, yet bugbot still needs re-confirmation against this HEAD. This branch is reachable only when state diverged BETWEEN ticks — for example, the user pushed a manual commit between two wakeups, leaving `current_head` ahead of the SHA bugbot last cleaned. Transition `phase = BUGBOT`, schedule next wakeup, return.
   - **bugteam reports findings without committing fixes:** apply the **Fix protocol** below (which always re-triggers bugbot after the push), transition `phase = BUGBOT`, schedule next wakeup, return.

### Step 3: Re-trigger bugbot

Used in Step 2 BUGBOT branch 1, in Step 2 BUGTEAM branch 1, and in the Fix protocol. Post a literal `bugbot run` PR comment. Write the body via the Write tool to a temp file, then pass it with `--body-file` (per the gh-body-file rule):

```bash
gh pr comment <NUMBER> --repo <OWNER>/<REPO> --body-file <path/to/bugbot_run.md>
```

The body file contains exactly the literal phrase `bugbot run` followed by a newline. Use that phrase exactly — empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

**Gotcha (duplicate `bugbot run` while a review is already queued):** Do not post another `bugbot run` when Bugbot has already picked up the latest trigger. On GitHub, the signal is an **eyes** (`:eyes:`) reaction on the **most recent** `bugbot run` PR comment (Bugbot acknowledging the job). When that reaction is present, skip Step 3 for this wait cycle - a second comment spams the PR and can confuse tick logic; wait for the review to finish or for `HEAD` to change before re-triggering per Step 2.

**Gotcha (Bugbot found errors, but a redundant `bugbot run` instead of a fix push):** When the latest Bugbot review on `current_head` still has **unaddressed findings** (inline threads and/or a non-clean review body), **do not** post another `bugbot run` on that same SHA as a substitute for fixing the code. A second trigger without a new commit cannot resolve the findings — it only duplicates noise and breaks tick expectations. Follow the **Fix protocol** end-to-end: implement fixes via **`Task` + `clean-coder`** in Cursor (never `generalPurpose` for code changes), **commit and push** so `HEAD` advances, reply inline on each thread, **then** Step 3 `bugbot run` against the new SHA.

### Step 3.5: Enforce the safety cap

Before Step 4 loop pacing, evaluate `tick_count`. When `tick_count >= 30`, stop and report per the **Stop conditions** safety-cap branch (§Safety cap) — **omit Step 4 entirely** (and stop the AHK auto-typer if it was started for this converge session). Reaching this many rounds means something structural is wrong with the loop and continuing wastes work. Otherwise proceed to Step 4.

### Step 4: Loop pacing (`ScheduleWakeup` or AHK fallback)

Throughout Step 2 and the Fix protocol, **schedule next wakeup, return** means: in **once mode**, return with no pacing; in **loop mode** (the default), execute this step.

**Once mode (opt-in single tick):** When the user message that started this run is exactly `/pr-converge once` (trimmed, ASCII case-insensitive), **skip this entire step** — no `ScheduleWakeup`, no AHK launcher instructions for pacing. The assistant runs one tick and stops.

**Loop mode (default):** Every other entry path: `/pr-converge`, `/loop /pr-converge`, an AHK `continue` tick, or a `ScheduleWakeup` whose `prompt` is `/pr-converge` or `/loop /pr-converge`.

In **loop mode**, pick **exactly one** pacing branch at the end of the tick (unless convergence or another stop condition already omitted pacing):

1. **`ScheduleWakeup` available in this session:** Call `ScheduleWakeup` with:

   - `delaySeconds: 270` whenever bugbot was just re-triggered (whether by Step 3 directly, by the Fix protocol's mandatory re-trigger, or by BUGTEAM branch 1's same-tick re-trigger). Bugbot finishes a review in 1–4 minutes, so 270s stays under the 5-minute prompt-cache TTL while giving a margin past bugbot's typical upper bound. The single exception is the BUGBOT inline-lag branch, which uses `delaySeconds: 60` because no re-trigger fired and the only thing being awaited is GitHub's inline-comments API catching up.
   - `reason`: one short sentence on what is being awaited, including the current `phase` and `bugbot_clean_at` SHA when set.
   - `prompt: "/pr-converge"` — re-enters this skill on the next firing with default loop semantics (no need for the user to type `/loop`). If the parent harness requires the `/loop` wrapper for wakeups to execute, `prompt: "/loop /pr-converge"` is equivalent.

2. **`ScheduleWakeup` not available:** Do not stop after a single tick. Follow [Alternative loop driver: AHK auto-continue](#alternative-loop-driver-ahk-auto-continue): on the **first** tick of this converge session in this environment, run **One-time setup** if the auto-typer is not already running; then follow **Per-tick behavior under this driver** (no `ScheduleWakeup` call; end with `Awaiting next "continue" tick.`).

**On convergence (loop mode):** omit `ScheduleWakeup`; if the AHK path was used, stop the auto-typer per **Convergence cleanup**.

## Fix protocol

Used by both phases when findings exist:

- Read each referenced file:line.
- Write a failing test first when the finding has behavior to test. For pure doc, comment, or naming nits with no behavior, go straight to the fix.
- Implement the fix.
- Stage the affected files and create one new commit on the existing branch:
  ```bash
  git add <files> && git commit -m "fix(review): <brief summary>"
  ```
  Honor pre-commit and pre-push hooks; when a hook rejects, read its message, fix the underlying issue, retry. Hook rejections flag real underlying issues worth investigating.
- Push the new commit:
  ```bash
  git push origin <BRANCH>
  ```
  Capture the new HEAD SHA. Set `current_head` to it. Set `bugbot_clean_at = null`.
- Reply inline on each addressed comment thread using `--body-file` (per gh-body-file rule):
  ```bash
  gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments/<comment_id>/replies \
    --field body=@<path/to/reply.md>
  ```
- **Always re-trigger bugbot (Step 3 above) after pushing a fix**, regardless of which phase originated the findings. Any new commit invalidates bugbot's prior clean by definition, so bugbot must re-review the new HEAD before convergence can be claimed. Re-triggering in the same tick saves a full wakeup cycle compared to deferring the trigger to the next tick.

## Stop conditions

- **Convergence** (back-to-back clean as defined in Step 2 BUGTEAM second branch — `bugteam reports convergence AND bugbot_clean_at == current_head` with no push during this tick): in **alternative mode**, post the BUGTEAM substitute audit to the PR (`gh pr comment --body-file`) **before** `gh pr ready`; then mark PR ready for review, report one-sentence summary, omit loop pacing (`ScheduleWakeup` and stop AHK if used).
- **Hard blocker:** API auth failure persists across two ticks, a CI regression whose root cause falls outside this PR, a hook rejection investigated through three commits and still unresolved, `inline_lag_streak >= 3`, or `/bugteam` itself reports a stuck state. Report the specific blocker and the diagnosis, then omit loop pacing and stop the AHK auto-typer if it was started.
- **User stops the loop:** user says "stop the converge loop" → omit loop pacing on the next tick and stop the AHK auto-typer if it was started.
- **Safety cap:** `tick_count >= 30` (evaluated in Step 3.5) → omit loop pacing, stop the AHK auto-typer if it was started, report the cap was hit. See §Safety cap below for rationale.

## Safety cap

When `tick_count >= 30`, stop and report. That many rounds means something structural is wrong with the loop. (Higher than copilot-review's 20-tick cap because two reviewers run sequentially per round.) The increment lives in Step 1; the evaluation lives in Step 3.5.

## Ground rules

- **Append commits.** Each tick adds at most one new fix commit. Multiple findings within one tick collapse into a single commit; the next tick handles the next round.
- **Bugbot findings on the current SHA mean fix-then-push-then-`bugbot run`, not another naked `bugbot run`.** Unaddressed Bugbot errors require the Fix protocol (implement, push, inline replies) before Step 3; posting `bugbot run` again without a new commit does not clear the review state.
- **`bugbot_clean_at` resets on every push.** A new commit invalidates bugbot's prior clean by definition — bugbot must re-review the new HEAD before convergence can be claimed.
- **Back-to-back clean is the ONLY termination criterion.** Convergence requires both reviewers clean against the same HEAD with no intervening fixes; either reviewer clean alone counts as in-progress.
- **Clean Bugbot on `HEAD` means advance to bugteam, not another `bugbot run`.** After Bugbot reports clean on the current SHA, the orchestrator must set `bugbot_clean_at` and run the **BUGTEAM** audit per Step 2 — never post `bugbot run` as a substitute. In Claude Code that is **`/bugteam`** via the skill tool; in **alternative mode** it is **parallel in-session `Task` + `code-quality-agent`** (`readonly: true`) for the audit (never `generalPurpose`), not a second Bugbot trigger.
- **The `bugbot run` comment is load-bearing.** Use the literal phrase `bugbot run` exactly — empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings silently no-op.
- **`gh pr ready` is the convergence action.** Mark the PR ready for review and stop there. In **alternative mode**, post the **BUGTEAM substitute audit digest** with **`gh pr comment --body-file`** on the PR **before** `gh pr ready` (see Step 2 branch d and [Gotchas](#gotchas)). Merge, additional reviewers, title, and body remain the user's decisions; the skill's contract ends at "ready for review."
- **Honor pre-push and pre-commit hooks.** When a hook rejects the change, read its output, fix the underlying issue (the failing test, the missing constant, the broken import), and retry.

## Examples

<example>
User: `/pr-converge`
Claude: [reads PR context, runs one tick of bugbot phase; in loop mode either schedules `ScheduleWakeup` at 270s with `prompt: "/pr-converge"` or, when that tool is missing, ensures AHK auto-continue is running and ends with `Awaiting next "continue" tick.`]
</example>

<example>
User: `/loop /pr-converge`
Claude: [same as `/pr-converge` default loop — one tick, then Step 4 pacing per harness]
</example>

<example>
User: `/pr-converge once`
Claude: [runs exactly one tick in once mode, reports state, skips Step 4 entirely — no wakeup, no AHK pacing instructions]
</example>

<example>
Tick fires in BUGBOT phase, latest bugbot review is against an older commit.
Claude: [posts `bugbot run` comment, sets `bugbot_clean_at = null`, schedules next wakeup at 270s, returns]
</example>

<example>
Tick fires in BUGBOT phase, bugbot has 2 unaddressed findings on HEAD.
Claude: [TDD-fixes both, one commit, pushes, replies inline on both threads, posts `bugbot run`, schedules next wakeup at 270s, returns]
</example>

<example>
Tick fires in BUGBOT phase, bugbot is clean against HEAD.
Claude: [sets `bugbot_clean_at = HEAD`, transitions `phase = BUGTEAM`, runs `/bugteam` in the same tick]
</example>

<example>
In BUGTEAM phase, /bugteam reports convergence and `bugbot_clean_at == current_head`.
Claude: [runs `gh pr ready <NUMBER>`, reports "PR converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for review", omits loop pacing, stops AHK if applicable]
</example>

<example>
In BUGTEAM phase, /bugteam pushed a fix commit during its run.
Claude: [re-resolves HEAD, sets `bugbot_clean_at = null`, posts `bugbot run` in this same tick, transitions `phase = BUGBOT`, schedules next wakeup at 270s]
</example>

<example>
Tick fires in BUGBOT phase, bugbot review body says "found 3 potential issues" against HEAD but the inline-comments API returns zero matching comments for `current_head`.
Claude: [increments `inline_lag_streak` to 1, schedules next wakeup at 60s, returns; expects inline comments to appear by the next tick]
</example>
