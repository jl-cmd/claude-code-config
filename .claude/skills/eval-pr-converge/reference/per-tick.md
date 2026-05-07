# Per-tick work

Use on **draft PR**. Cursor Bugbot and `/eval-bugteam` re-run after each push. Fix
findings between rounds until back-to-back clean on same `HEAD`, then mark
PR ready for review.

Run every tick in parent harness session. Pacing lives in
[`../workflows/schedule-wakeup-loop.md`](../workflows/schedule-wakeup-loop.md) (read before Step 4); see [Pacing
workflow](#pacing-workflow).

Every eval-bugteam tick runs **eval-bugteam** — never hand-rolled substitute. Fix
protocol per [fix-protocol.md](fix-protocol.md). Pacing stays in main session via
`ScheduleWakeup` (pre-flight aborts when absent).

## Invocation modes

- **`/eval-pr-converge`** runs one tick, then Step 4 schedules the next via
  `ScheduleWakeup`. Omit the next wakeup only on convergence or **Stop
  conditions**.

## Pacing workflow

Read [`../workflows/schedule-wakeup-loop.md`](../workflows/schedule-wakeup-loop.md)
(installed copy under `$HOME/.claude/skills/eval-pr-converge/workflows/`) before
Step 4. The pre-flight gate guarantees `ScheduleWakeup` is invokable; the
workflow file specifies delays, prompts, convergence cleanup, and
inline-lag handling.

- **`/eval-pr-converge`** (default): loops until convergence. After each tick
  (unless converged or stopped), run **Step 4**.

## Step 1: Resolve current HEAD and PR context

Read prior tick's state line from most recent assistant message (or
initialize fields if none). Increment `tick_count` by 1 in conversation
state line when **no** `state.json` (single-PR only). With `state.json`, do
**not** increment here — orchestrator's per-tick bump is sole increment.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/view_pr_context.py"
```

Capture `number`, `headRefOid` (= `current_head`), owner/repo, branch.

## Step 2: Branch on `phase`

### `phase == BUGBOT`

a. Fetch Cursor Bugbot reviews newest-first, walk back until first clean:

   ```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_bugbot_reviews.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
   ```

Track dirty entries in a temp file; Fix protocol reads it back later
this tick.

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

c. Decide (four branches; match first whose predicate holds):
   - **No bugbot review yet, OR latest review's `commit_id` ≠
     `current_head`:** Re-trigger bugbot (Step 3), set `bugbot_clean_at =
     null`, reset `inline_lag_streak = 0`, schedule next wakeup, return.
   - **`commit_id == current_head` AND zero unaddressed inline AND review
     body clean:** Set `bugbot_clean_at = current_head`, reset
     `inline_lag_streak = 0`, `phase = eval-bugteam`. Continue eval-bugteam in same
     tick — back-to-back convergence requires eval-bugteam on same HEAD
     before next wakeup.
   - **`commit_id == current_head` with unaddressed inline findings:**
     Apply **Fix protocol**. Reset `inline_lag_streak = 0`. With
     `state.json`: eval-eval-clean-coder teammate pushes, replies inline, writes
     `state.json`, goes idle; Step 3 on new HEAD runs after via
     orchestrator-spawned follow-up agent (§Fix result → general-purpose).
     No `state.json` (single-PR): implement → push → inline replies
     → Step 3 in same tick per loaded pacing workflow. Schedule next
     wakeup, return.
   - **`commit_id == current_head` AND review body findings AND inline
     API zero matching for `current_head`:** Transient API lag. Increment
     `inline_lag_streak`. `>= 3` → hard blocker; report and terminate with
     no loop pacing. Else Step 4 uses the BUGBOT inline-lag section of
     `../workflows/schedule-wakeup-loop.md` (`delaySeconds: 90`).

### `phase == eval-bugteam`

a. Run **eval-bugteam** on current PR.

   - **`Skill` invokable**: invoke eval-bugteam
     with `Skill`.

     ```
Skill({skill: "eval-bugteam", args:
"https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"})
     ```

   - **`Skill` not invokable** (typical delegated teammate): worker executes
     eval-bugteam by reading [`../../eval-eval-bugteam/SKILL.md`](../../eval-eval-bugteam/SKILL.md). Same
     loop and gates; only harness steps differ.

b. **Re-resolve current HEAD** — eval-bugteam may have pushed commits during
its run. `current_head` from Step 1 is potentially stale:
   ```bash
new_head=$(python "${CLAUDE_SKILL_DIR}/scripts/resolve_pr_head.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>)
   ```
If `new_head != current_head`, set `current_head = new_head` AND
`bugbot_clean_at = null`. New commits invalidate bugbot's prior clean.

c. Inspect eval-bugteam outcome. Reports `convergence (zero findings)` or list
of unfixed findings with file:line.

d. Decide based on post-eval-bugteam state — order matters. Check
pushed-during-eval-bugteam FIRST so convergence report against stale HEAD
never falsely terminates:
   - **Audit pushed this tick (`bugbot_clean_at` reset in step b):**
     Re-trigger bugbot same tick (Step 3) so new HEAD enters queue, `phase
     = BUGBOT`, schedule next wakeup, return.
   - **Convergence AND `bugbot_clean_at == current_head` (no push):**
     Back-to-back clean — necessary, not sufficient. Run the **pre-Copilot
     lint pass** described below. When the lint pass returns clean, run
     **[convergence-gates.md](convergence-gates.md)** to clear Copilot-findings,
     mergeability, post-convergence Copilot-request. When the lint pass
     surfaces actionable findings, treat them as a fix loop (apply
     **[fix-protocol.md](fix-protocol.md)** to every finding the pass
     produced; push; reset `bugbot_clean_at = null`; `phase = BUGBOT`;
     re-trigger bugbot via Step 3 on new HEAD; schedule next wakeup; return).
     Only when all four gates pass mark PR ready and **omit loop pacing**
     per **Convergence** of active pacing workflow.
   - **Convergence BUT `bugbot_clean_at != current_head` (no push):**
     `phase = BUGBOT`, schedule next wakeup, return.
   - **Findings without committed fixes:** apply **[fix-protocol.md](fix-protocol.md)**; Step 3
     on new HEAD runs after fix handoff per `multi-pr-orchestration.md` or in-tick for
     single-PR. `phase = BUGBOT`, schedule next wakeup, return.

## Step 3: Re-trigger bugbot

Prefer portable script (temp body file, `gh pr comment --body-file`):

```bash
python "${CLAUDE_SKILL_DIR}/scripts/trigger_bugbot.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
```

**Bundled PowerShell alternative** (same gh-body-file contract):

```bash
POST_BUGBOT_RUN="$HOME/.claude/skills/eval-pr-converge/scripts/post-bugbot-run.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "$POST_BUGBOT_RUN" \
"https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"
```

`bugbot run` is empirically the only re-trigger Cursor Bugbot recognizes;
alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

**Gotcha (duplicate `bugbot run` while review queued):** Skip Step 3 when
the latest `bugbot run` PR comment has an `:eyes:` or `:+1:` reaction; wait
for review or HEAD change before re-triggering.

## Pre-Copilot lint pass

Runs after bugbot CLEAN ∧ eval-bugteam CLEAN at `current_head`, before
convergence-gates.md §(c) requests Copilot review. The pass exists because
Copilot consistently catches a narrow set of categories that bugteam's audit
rubric does not surface, and each such finding becomes a Copilot rejection
round. Catching the same patterns locally before requesting review eliminates
the round.

The pass is a focused audit against the diff at `current_head`, scoped to
exactly four categories. For each category, scan every changed file in the
diff:

1. **Eager default evaluation.** Look for `dict.get(key, expensive_or_lossy_default())`,
   `or` short-circuit defaults that always evaluate the right operand,
   `getattr(obj, attr, fallback())` patterns where `fallback()` has cost
   or side effects, and ternaries that compute the unused branch. When the
   default is non-trivial (function call, dict allocation, lookup that
   re-reads state), file a finding to gate the default behind a membership
   or presence check.
2. **Type-contract vs runtime.** For every signature touched in the diff,
   check whether `Optional[T]`, `Union[A, B]`, or `T | None` parameters are
   handled in the body for every constituent. When the body assumes the
   non-`None` branch only and the function is reachable with `None` from
   any caller in the diff or in `git grep` of the symbol, file a finding
   asking for an explicit `if x is None: raise ValueError(...)` guard at
   function entry, OR for the signature to narrow to the runtime contract.
3. **Log-message accuracy.** For every new or modified `logger.info`,
   `logger.warning`, `logger.error`, `print`, or `sys.std{out,err}.write`
   call site in the diff, read the message text and compare it to the
   surrounding code's behavior. When the message describes an action the
   code does not actually perform (e.g., "moved to Trash" when the code
   marks read-and-keep, "retrying" when the code returns immediately), file
   a finding citing the exact divergence.
4. **dict.get fallback semantics.** Look for `mapping.get(key)` where the
   None-result is then passed into code that requires a non-None value.
   When the call site cannot tolerate None (subscript, attribute access,
   arithmetic, format-string substitution that would yield "None"), file a
   finding asking for either a presence-check branch OR a `mapping[key]`
   subscript that raises `KeyError` deterministically.

The pass reports findings in the same shape as eval-bugteam audit findings
(`finding_id`, `severity`, `category`, `file`, `line`, `description`).
Severity for pre-Copilot findings is always `P1` (would-be-Copilot-finding,
worth fixing before requesting review). When the pass returns zero findings,
record `pre_copilot_lint_at = current_head` in the state line and continue
to convergence-gates.md §(c). The flag remains valid until the next push.

## Step 4: Loop pacing

**`ScheduleWakeup` field hints** (prefer [Pacing
workflow](#pacing-workflow)):

- `delaySeconds: 270` after bugbot re-trigger. Bugbot finishes in 1–4
  min; 270s stays under 5-min prompt-cache TTL with margin. Exception:
  BUGBOT inline-lag branch uses `delaySeconds: 90` (no re-trigger;
  awaiting GitHub inline API).
- `reason`: short sentence on what is awaited, including `phase` and
  `bugbot_clean_at` SHA.
- `prompt: "/eval-pr-converge"`.

**On convergence:** apply **Convergence** section of
`../workflows/schedule-wakeup-loop.md` (omit wakeups).

## eval-bugteam execution

**Second audit** (eval-bugteam phase) is **always** **eval-bugteam** skill: preflight,
CODE_RULES gate, **`eval-eval-code-quality-agent`** / **`eval-eval-clean-coder`** loop, audit
rubric, outcome shape, Step 2 eval-bugteam §(b)–(d) contract — all in
[`../../eval-eval-bugteam/SKILL.md`](../../eval-eval-bugteam/SKILL.md) plus `PROMPTS.md` / `EXAMPLES.md` /
`CONSTRAINTS.md`. Do not re-spec.

**eval-pr-converge rule:** Prefer **`Skill({skill: "eval-bugteam", args: "<PR URL or
args>"})`** wherever registry exposes `Skill`. When `Skill` not invokable
(typical delegated teammate), worker runs **eval-bugteam** by loading
`../../eval-eval-bugteam/SKILL.md` from the same checkout. If eval-bugteam cannot run, cancel the
convergence loop fully and report the issue to the user.
