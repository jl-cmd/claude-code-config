---
name: pr-converge
description: >-
  Drives the current PR to convergence by alternating Cursor Bugbot and the
  in-house second audit (bugteam when Claude Code agent teams are enabled, else
  a simple background agent per PR). Each invocation runs one tick of work in the main
  session: fetches the latest reviewer state, applies TDD fixes for any
  findings, pushes one commit per tick, replies inline, and re-triggers the
  reviewer. To loop automatically where supported, invoke as `/loop /pr-converge`
  so ScheduleWakeup paces re-entry. When `/loop` or `ScheduleWakeup` is unavailable,
  follow §Loop cycle without `/loop` or ScheduleWakeup in this skill body.
  Convergence requires a
  back-to-back clean cycle (bugbot CLEAN immediately followed by second-audit CLEAN
  with no intervening fixes), at which point the PR is flipped to ready for
  review and the loop terminates. Triggers: '/pr-converge', 'drive PR to
  convergence', 'loop bugbot and bugteam', 'babysit bugbot and bugteam',
  'until both are clean', 'converge this PR'.
---

# PR Converge

Runs one tick of the bugbot ↔ bugteam convergence loop in the main session. Designed to be invoked under `/loop /pr-converge` so the parent's ScheduleWakeup paces re-entry when that harness exists. Self-terminates the loop on convergence (back-to-back clean) by flipping the PR to ready for review and omitting the next ScheduleWakeup. When `/loop` is unavailable, see **§Loop cycle without `/loop` or ScheduleWakeup**.

## Why the work runs in the main session, not a background subagent

`ScheduleWakeup` is a primitive of the parent harness; it is not exposed to `general-purpose` subagents. A prior version of this skill spawned a background subagent and instructed it to call `ScheduleWakeup` at the end of each tick. The subagent's tool registry returned "No matching deferred tools found" for `ScheduleWakeup`, so the loop could never self-perpetuate — it ran exactly one tick and stalled. Running the loop in the main session via `/loop /pr-converge` puts the work on the same harness that owns `ScheduleWakeup`, eliminating that failure mode.

## When this skill applies

The user is on a PR branch and wants both reviewers — Cursor's Bugbot AND the in-house `/bugteam` audit — to keep re-reviewing after each push, with findings auto-addressed between ticks. The PR stays in draft until convergence; on convergence the skill flips it to ready for review.

## Second-audit execution (team vs Cursor)

The **second audit** (BUGTEAM phase) is either the `/bugteam` skill (Claude Code agent teams) or **one simple background agent per PR** (no `TeamCreate`) that must produce the **same downstream contract** as `/bugteam` for Step 2 BUGTEAM §(b)–(d): optional commits on `current_head`, convergence or findings list, same fix and re-trigger behaviour.

### Team infrastructure detection

At the start of BUGTEAM step **(a)** each tick, evaluate **once**:

- **Team infrastructure present** when the environment variable `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is set and its value equals **`1`** after trimming leading and trailing whitespace. This matches the bugteam skill's requirement for Claude Code agent teams (`packages/claude-dev-env/skills/bugteam/CONSTRAINTS.md`).
- **Otherwise** (unset, any other value, or host never exports this variable — typical Cursor IDE sessions): team infrastructure is **absent**. Do **not** invoke `Skill({skill: "bugteam", ...})` or rely on `TeamCreate`; use the **non-team background-agent** branch in BUGTEAM step **(a)** instead.

### Background-agent second audit (when team infrastructure is absent)

This path **replaces** agent teams with **simple background agents** — ordinary delegated workers (for example `general-purpose` with `run_in_background: true` where the host exposes that), **not** `TeamCreate` bugfind/bugfix teammates. The orchestrator **only spawns and waits**; it does **not** substitute for those agents by reading the diff, auditing files, or editing code inline.

Each background agent runs, inside its own session:

1. The same **preflight** and **code-rules gate** the bugteam lead runs before spawning bugfind: `bugteam_preflight.py` then `bugteam_code_rules_gate.py --base origin/<BASE>` from the packaged dev-env tree (`${CLAUDE_DEV_ENV_ROOT}` / `${CLAUDE_SKILL_DIR}` / repo docs as in bugteam `SKILL.md`). If scripts are not on disk, follow the repository's documented gate substitute (for example `.cursor/BUGBOT.md` where that file exists in the checkout).
2. **One** full second-audit pass over the PR scope: apply `CODE_RULES.md` and the bugteam audit rubric (`bugteam/reference/audit-contract.md`), producing either **convergence (zero findings)** or a **findings list with `file:line`** in the same shape `/bugteam` uses so Step **(c)** can branch unchanged.
3. Returns that outcome to the orchestrator as the handoff payload (the agent does **not** call `TeamCreate` or `Skill({skill: "bugteam", ...})`; it performs the equivalent work itself).

All later steps in this tick treat that outcome as **the second audit** where §(b)–(d) reference **bugteam** semantics (pushes, convergence, findings).

Reporting: when marking converged, the one-line report uses **`bugteam CLEAN`** if the team path ran; use **`cursor audit CLEAN`** if the background-agent path ran.

## Multi-PR orchestration model

### Core rule: orchestrator is a traffic controller only

The orchestrator (main session) **never** reads files, writes code, audits findings, or does any per-PR work inline. It receives results, reads the state file, and spawns the correct teammate. Every unit of actual work runs inside a dedicated teammate.

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
  5. **Writes its result to `state.json`** (per §Concurrency) (`last_action: "fix_pushed"`, `current_head: <new SHA>`, `bugbot_clean_at: null`, `phase: "BUGBOT"`).
  6. Goes idle.

- For PRs with zero findings: spawn **one `general-purpose` agent** per PR. That agent:
  1. If `bugbot_clean_at == current_head` (back-to-back clean): run `mark_pr_ready.py`, then **write `state.json`** (per §Concurrency) setting this PR's entry to at least `status: "converged"`, `last_action: "converged"` (or `marked_ready`), `phase: "BUGBOT"`, and `last_updated` to an ISO-8601 UTC timestamp — **before** going idle. Omitting this write leaves the orchestrator on later ticks with a stale `awaiting_bugteam` / `in_progress` row and risks duplicate work.
  2. Otherwise: update `state.json` (per §Concurrency) with `last_action: "audit_clean"`, `status: "awaiting_bugbot"`, `phase: "BUGBOT"`, then trigger bugbot via `trigger_bugbot.py`.
  3. Goes idle.

#### Fix result → general-purpose per PR

When a bugfix (clean-coder) teammate goes idle after pushing a fix:

- Spawn **one `general-purpose` agent** per PR. That agent:
  1. Reads `state.json` for its PR.
  2. Triggers bugbot via `trigger_bugbot.py`.
  3. Polls `fetch_bugbot_reviews.py` every 60s (up to 10 polls) until a review anchored to `current_head` appears.
  4. Fetches inline comments via `fetch_bugbot_inline_comments.py`.
  5. Classifies result: `clean` (review body clean + zero inline) or `dirty` (findings exist).
  6. **Writes result to `state.json`** (per §Concurrency): sets `bugbot_clean_at` (if clean) or records findings count, updates `last_action`, `status`, and **`phase`**: `BUGTEAM` when the outcome is `clean` (next work is second audit), `BUGBOT` when the outcome is `dirty` (next work is another fix pass).
  7. Reports back to orchestrator: one-line summary of outcome.

- Orchestrator reads the updated `state.json` and spawns the appropriate next agent:
  - Result `clean` → spawn a `general-purpose` agent to run BUGTEAM phase (invokes bugteam skill **or** §Background-agent second audit per §Second-audit execution, whichever applies at runtime).
  - Result `dirty` → spawn a `clean-coder` agent to fix the new findings (same as "audit result with findings" above).

### What the orchestrator does per tick

1. Perform the **per-tick `tick_count` bump** in §Orchestrator `state.json` writes (traffic metadata only) for every non-terminal PR under `prs`.
2. Read `state.json`.
3. For each PR with new teammate results (idle notifications), spawn the next agent per the rules above — all in one parallel message.
4. Re-read `state.json` if needed for scheduling; **Step 3.5** uses each PR's `tick_count` from this file (or the conversation state line when no `state.json` exists — single-PR-only invocation).
5. Call `ScheduleWakeup` with the appropriate delay.
6. Nothing else.

## Invocation modes

- **`/loop /pr-converge`** (recommended): loops automatically. The /loop skill runs each tick and uses ScheduleWakeup to pace re-entry. Termination on convergence is automatic; the skill omits the next wakeup at the convergence tick.
- **`/pr-converge`** (manual): runs exactly one tick and returns. Useful for ad-hoc state checks or for advancing the loop one step manually. The user re-runs the skill (or wraps it in `/loop`) to continue.

## Loop cycle without `/loop` or ScheduleWakeup

Some hosts expose **neither** `/loop` nor `ScheduleWakeup`. There is still **no in-model timer**; the **only** substitute this skill defines is an **OS-level scheduled job** the operator installs once.

**Harness (normative):** use **cron** (Unix), **systemd timer** (Linux services), or **Windows Task Scheduler** to run on a **fixed wall-clock interval of 270 seconds** (same default as Step 4 `delaySeconds` — long enough for Bugbot, under typical cache TTL). Each run executes **exactly one** non-interactive agent invocation using the **product's documented** "single prompt from file / stdin" CLI or API entrypoint. The job's input is a **constant** one-tick instruction: run §Per-tick work for the target PR; read prior state from disk; write updated state to disk; exit zero on success.

**State on disk (required for this harness):** prior tick output must live where the next run can read it without chat history — for multi-PR use `<TMPDIR>/pr-converge-<session_id>/state.json` (§Per-PR state file); for a single PR without that file, the operator picks **one absolute path** to a small JSON file, passes it to every run (argument or environment), creates it on the first tick, and updates it every tick. The scheduled command must wire that path into the frozen prompt or process environment the agent reads.

**Enforceability:** the OS records whether each run started and its exit code (cron logs, `journalctl`, Task Scheduler **Last Run Result**). A missed tick or failing process is visible to operators; the model cannot "silently skip" the schedule.

**Step 4 in these hosts:** `ScheduleWakeup` calls are **omitted**; the **next** tick is whichever **scheduled OS run** fires next. Do not delegate re-entry to a background subagent calling `ScheduleWakeup` on hosts where that tool does not exist (see §Why the work runs in the main session).

## State across ticks

Track the following in plain text in the assistant's response so subsequent ticks can re-read it from conversation context:

- `phase`: `BUGBOT` or `BUGTEAM`. Start in `BUGBOT` on the first tick of a fresh loop.
- `bugbot_clean_at`: the HEAD SHA at which bugbot last reported clean, or `null`. Reset to `null` whenever a new commit is pushed.
- `inline_lag_streak`: integer counter, initialized to `0`. Tracks consecutive ticks where bugbot's review body indicates findings against `current_head` but the inline-comments API returns zero matching comments. Reset to `0` on any other branch outcome.
- `tick_count`: integer, initialized to `0`. Increment on every tick to enforce the safety cap.

Each tick begins by reading the prior tick's state line from the most recent assistant message and ends by emitting the updated state line.

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
   - **No bugbot review yet, OR latest bugbot review's `commit_id` differs from `current_head`:** Re-trigger bugbot (Step 3), set `bugbot_clean_at = null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND zero unaddressed inline findings AND review body indicates clean:** Set `bugbot_clean_at = current_head`. Reset `inline_lag_streak = 0`. Transition `phase = BUGTEAM`. Continue to bugteam branch in this same tick — back-to-back convergence requires bugteam to run against the same HEAD before the next wakeup is scheduled.
   - **Latest review's `commit_id == current_head` with unaddressed inline findings (review body indicates findings):** Apply the **Fix protocol** below to address them. Reset `inline_lag_streak = 0`. The fix protocol pushes a new commit, which sets `current_head` to the new SHA, sets `bugbot_clean_at = null`, and replies inline on each thread; **Step 3** (`trigger_bugbot.py` on the new HEAD) runs **after** the fix teammate goes idle, via the orchestrator-spawned follow-up agent (§Fix protocol). Schedule next wakeup, return.
   - **Latest review's `commit_id == current_head` AND review body indicates findings AND inline-comments API returns zero matching comments for `current_head`:** Treat as transient API propagation lag — bugbot publishes the review body and inline comments through separate API operations and the two writes can briefly desync. Increment `inline_lag_streak`. When `inline_lag_streak >= 3`, escalate as a hard blocker (bugbot review is structurally inconsistent — body claims findings while inline anchors stay empty across three consecutive ticks); report and terminate. Otherwise schedule next wakeup at `delaySeconds: 60` (lag is short-lived) and return; the inline comments should appear on the next tick.

#### `phase == BUGTEAM`

a. Run the **second audit** on the current PR. Branch on §Team infrastructure detection:

   - **Team path** (team infrastructure **present**): invoke the `Skill` tool in the main session:

     ```
     Skill({skill: "bugteam", args: "https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"})
     ```

     The main session is the team lead, so `TeamCreate` fires from the orchestrator and `/bugteam` emits its CODE_RULES gate output, teammate spawn lines, and audit progress as expected. The skill audits the current PR against CODE_RULES, posts review threads, and converges or stops at its own internal cap. Wait for it to complete; capture exit and final summary.

   - **Non-team path** (team infrastructure **absent**): spawn **one** simple **background** `general-purpose` agent per PR whose sole job is §Background-agent second audit. Wait until it completes (join or completion notification, per host). Capture the same class of summary you would from `/bugteam` (convergence vs findings) for Step **(c)**. The orchestrator does not perform that audit inline.

b. **Re-resolve current HEAD now** because the second audit may have pushed commits during its run. The `current_head` from Step 1 is potentially stale at this point:
   ```bash
   new_head=$(python "${CLAUDE_SKILL_DIR}/scripts/resolve_pr_head.py" \
     --owner <OWNER> --repo <REPO> --number <NUMBER>)
   ```
   If `new_head != current_head`, set `current_head = new_head` AND set `bugbot_clean_at = null`. The new commits from the second audit invalidate bugbot's prior clean.

c. Inspect the second audit output. It reports either `convergence (zero findings)` or a list of unfixed findings with file:line (same semantics as `/bugteam`).

d. Decide based on the (post-second-audit) state — order matters; check pushed-during-second-audit FIRST so a convergence report against a stale HEAD never falsely terminates:
   - **Second audit pushed during this tick (i.e., `bugbot_clean_at` was just reset to `null` in step b):** Re-trigger bugbot in this same tick (Step 3) so the new HEAD enters bugbot's queue immediately, transition `phase = BUGBOT`, schedule next wakeup, return. The new commit needs a fresh bugbot review before convergence can be claimed.
   - **Second audit reports convergence AND `bugbot_clean_at == current_head` (no push during this tick):** This is back-to-back clean. Mark the PR ready for review:
     ```bash
     python "${CLAUDE_SKILL_DIR}/scripts/mark_pr_ready.py" \
       --owner <OWNER> --repo <REPO> --number <NUMBER>
     ```
     Report to the user in one sentence: `PR #<NUMBER> converged: bugbot CLEAN at <SHA>, <SECOND_AUDIT_LABEL> CLEAN at <SHA>; marked ready for review` where `<SECOND_AUDIT_LABEL>` is **`bugteam`** if the team path ran or **`cursor audit`** if the background-agent path ran. **Omit the next ScheduleWakeup call** — this terminates the /loop.
   - **Second audit reports convergence BUT `bugbot_clean_at != current_head` (no push during this tick):** The second audit reached zero findings without committing, yet bugbot still needs re-confirmation against this HEAD. This branch is reachable only when state diverged BETWEEN ticks — for example, the user pushed a manual commit between two wakeups, leaving `current_head` ahead of the SHA bugbot last cleaned. Transition `phase = BUGBOT`, schedule next wakeup, return.
   - **Second audit reports findings without committing fixes:** apply the **Fix protocol** below; **Step 3** on the new HEAD still runs **after** the fix teammate's handoff through the follow-up agent (§Fix protocol), not inside the fix teammate. Transition `phase = BUGBOT`, schedule next wakeup, return.

### Step 3: Re-trigger bugbot

Used in Step 2 BUGBOT branch 1, in Step 2 BUGTEAM branch 1, and in the Fix protocol. The script writes a temp file containing the literal phrase `bugbot run\n`, posts it via `gh pr comment --body-file` (per the gh-body-file rule), and removes the temp file:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/trigger_bugbot.py" \
  --owner <OWNER> --repo <REPO> --number <NUMBER>
```

`bugbot run` is empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

### Step 3.5: Enforce the safety cap

Before scheduling the next wakeup, evaluate **`tick_count`**: for multi-PR runs, when **any** `prs[<pr_number>].tick_count >= 30`; for single-PR-only runs (no `state.json`), when the conversation state line's `tick_count >= 30`. When the cap trips, stop and report per the **Stop conditions** safety-cap branch (§Safety cap) — **omit Step 4 entirely**. Reaching this many rounds means something structural is wrong with the loop and continuing wastes work. Otherwise proceed to Step 4.

### Step 4: Schedule the next wakeup (only when invoked under `/loop`)

**Skip this step entirely when the skill was invoked as bare `/pr-converge`** (manual mode). **Skip it also when the host exposes no `ScheduleWakeup` tool** (many IDE-only environments): there is nothing to call; one tick ends and §Loop cycle without `/loop` or ScheduleWakeup owns re-entry. Manual mode runs exactly one tick and returns without scheduling — the user re-runs the skill or wraps it in `/loop` to continue when `/loop` exists. References elsewhere in this document to "schedule next wakeup, return" mean Step 4 below; when Step 4 is skipped, every such reference becomes "return" only.

Detect **loop mode** (Step 4 eligible) only when **both** hold: the host supports `ScheduleWakeup`, **and** the run was triggered by the parent's `/loop` wakeup chain or the user typed `/loop /pr-converge`. When the most recent user message was bare `/pr-converge` (no `/loop` prefix and no such wakeup chain), or when `ScheduleWakeup` is unavailable, treat as **manual / no-harness mode** for Step 4.

In **loop mode**, call `ScheduleWakeup` with:

- `delaySeconds: 270` whenever bugbot was just re-triggered (whether by Step 3 directly, by **Step 3** after a fix via the follow-up agent chain, or by BUGTEAM branch 1's same-tick re-trigger). Bugbot finishes a review in 1–4 minutes, so 270s stays under the 5-minute prompt-cache TTL while giving a margin past bugbot's typical upper bound. The single exception is the BUGBOT inline-lag branch, which uses `delaySeconds: 60` because no re-trigger fired and the only thing being awaited is GitHub's inline-comments API catching up.
- `reason`: one short sentence on what is being awaited, including the current `phase` and `bugbot_clean_at` SHA when set.
- `prompt: "/loop /pr-converge"` — re-enters this skill via /loop on the next firing.

**On convergence (loop mode):** omit the ScheduleWakeup call entirely. The /loop terminates because no next wakeup was scheduled.

## Fix protocol

The fix protocol is executed by a **`clean-coder` teammate**, never inline by the orchestrator. The orchestrator spawns the teammate with the findings context; the teammate:

- Reads each referenced file:line.
- Writes a failing test first when the finding has behavior to test. For pure doc, comment, or naming nits, goes straight to the fix.
- Implements the fix.
- Stages affected files and creates one new commit:
  ```bash
  git add <files> && git commit -m "fix(review): <brief summary>"
  ```
  Honours pre-commit and pre-push hooks; when a hook rejects, reads the message, fixes the issue, retries.
- Pushes:
  ```bash
  git push origin <BRANCH>
  ```
- Replies inline on each addressed finding thread via `reply_to_inline_comment.py` (what changed and the commit identifier), matching §Audit result → clean-coder step 4 — **before** writing `state.json` and going idle.
- Writes `last_action: "fix_pushed"`, `current_head: <new SHA>`, `bugbot_clean_at: null`, `phase: "BUGBOT"` to `state.json` (per §Concurrency).
- Goes idle. The orchestrator spawns the follow-up `general-purpose` agent for bugbot trigger and monitoring.

**The orchestrator does not reply to inline comments, does not trigger bugbot, and does not read file contents during the fix phase.** Those actions belong to the dedicated per-PR agents.

## Stop conditions

- **Convergence** (back-to-back clean as defined in Step 2 BUGTEAM second branch — second audit reports convergence AND `bugbot_clean_at == current_head` with no push during this tick): mark PR ready for review, report one-sentence summary, omit ScheduleWakeup.
- **Hard blocker:** API auth failure persists across two ticks, a CI regression whose root cause falls outside this PR, a hook rejection investigated through three commits and still unresolved, `inline_lag_streak >= 3`, or the second audit (`/bugteam` or background-agent pass) reports a stuck state. Report the specific blocker and the diagnosis, then omit ScheduleWakeup.
- **User stops the loop:** user says "stop the converge loop" → omit ScheduleWakeup on the next tick.
- **Safety cap:** any tracked `tick_count >= 30` (evaluated in Step 3.5) → omit ScheduleWakeup, report the cap was hit. See §Safety cap below for rationale.

## Safety cap

When `tick_count >= 30`, stop and report. That many rounds means something structural is wrong with the loop. (Higher than copilot-review's 20-tick cap because two reviewers run sequentially per round.) The increment lives in Step 1; the evaluation lives in Step 3.5.

## Ground rules

- **Append commits.** Each tick adds at most one new fix commit. Multiple findings within one tick collapse into a single commit; the next tick handles the next round.
- **`bugbot_clean_at` resets on every push.** A new commit invalidates bugbot's prior clean by definition — bugbot must re-review the new HEAD before convergence can be claimed.
- **Back-to-back clean is the ONLY termination criterion.** Convergence requires Bugbot clean and the second audit (bugteam or background-agent pass) clean against the same HEAD with no intervening fixes; either side clean alone counts as in-progress.
- **The `bugbot run` comment is load-bearing.** Use the literal phrase `bugbot run` exactly — empirically the only re-trigger Cursor Bugbot recognizes; alternative phrasings silently no-op.
- **`gh pr ready` is the convergence action.** Mark the PR ready for review and stop there. Merge, additional reviewers, title, and body remain the user's decisions; the skill's contract ends at "ready for review."
- **Honor pre-push and pre-commit hooks.** When a hook rejects the change, read its output, fix the underlying issue (the failing test, the missing constant, the broken import), and retry.

## Examples

<example>
User: `/loop /pr-converge`
Claude: [reads PR context, runs one tick of bugbot phase, schedules next wakeup at 270s with prompt `/loop /pr-converge`, returns]
</example>

<example>
User: `/pr-converge`
Claude: [runs one tick manually, reports state, does NOT schedule a wakeup; user re-runs to advance]
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
Claude: [runs `gh pr ready <NUMBER>`, reports "PR converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for review", omits ScheduleWakeup, terminates the /loop]
</example>

<example>
In BUGTEAM phase, /bugteam pushed a fix commit during its run.
Claude: [re-resolves HEAD, sets `bugbot_clean_at = null`, posts `bugbot run` in this same tick, transitions `phase = BUGBOT`, schedules next wakeup at 270s]
</example>

<example>
Tick fires in BUGBOT phase, bugbot review body says "found 3 potential issues" against HEAD but the inline-comments API returns zero matching comments for `current_head`.
Claude: [increments `inline_lag_streak` to 1, schedules next wakeup at 60s, returns; expects inline comments to appear by the next tick]
</example>

<example>
BUGTEAM tick with no agent teams: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is unset; team infrastructure absent.
Claude: [spawns one background `general-purpose` agent whose prompt is §Background-agent second audit; waits for handoff; applies Step 2 §(b)–(d) unchanged against that agent's outcome]
</example>
