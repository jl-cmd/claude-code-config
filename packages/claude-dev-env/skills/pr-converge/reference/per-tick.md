# Per-tick work

Use on **draft PR**. Cursor Bugbot and `/bugteam` re-run after each push. Fix
findings between rounds until back-to-back clean on same `HEAD`, then mark
PR ready for review.

Run every tick in parent harness session. Pacing lives in
[`../workflows/schedule-wakeup-loop.md`](../workflows/schedule-wakeup-loop.md) (read before Step 4); see [Pacing
workflow](#pacing-workflow).

Every BUGTEAM tick runs **bugteam** — never hand-rolled substitute. Fix
protocol per [fix-protocol.md](fix-protocol.md). Pacing stays in main session via
`ScheduleWakeup` (pre-flight aborts when absent).

## Invocation modes

- **`/pr-converge`** runs one tick, then Step 4 schedules the next via
  `ScheduleWakeup`. Omit the next wakeup only on convergence or **Stop
  conditions**.

## Pacing workflow

Read [`../workflows/schedule-wakeup-loop.md`](../workflows/schedule-wakeup-loop.md)
(installed copy under `$HOME/.claude/skills/pr-converge/workflows/`) before
Step 4. The pre-flight gate guarantees `ScheduleWakeup` is invokable; the
workflow file specifies delays, prompts, convergence cleanup, and
inline-lag handling.

- **`/pr-converge`** (default): loops until convergence. After each tick
  (unless converged or stopped), run **Step 4**.

## Step 0: Ensure on PR branch (worktree-aware)

Before any GitHub interaction, confirm the session is on the PR's actual
branch. If the PR branch is checked out in a different git worktree, the
current session must switch into that worktree — pushing from a
differently-named local branch to the PR branch via refspec silently works,
but the divergence surface grows with every tick and rebase/history
operations become unsafe.

1. Resolve the PR's head ref from the API:
   ```
   pull_request_read(method="get", pullNumber=N, owner=O, repo=R) → `.head.ref`
   ```
2. Run ``git branch --show-current`` in the current session. If it matches
   `.head.ref`, continue to Step 1.
3. If it does NOT match, run ``git worktree list``. Scan for the entry whose
   branch column matches `.head.ref`.
   - **Found:** call `EnterWorktree(path=<that worktree path>)` to switch
     the session into the correct worktree, then continue to Step 1.
   - **Not found:** the PR branch is not checked out anywhere. Create a
     fresh worktree: `git worktree add <temp_dir>/pr-<N>-worktree
     origin/<head.ref>`, then `EnterWorktree(path=<that path>)`.
4. After switching, `git fetch origin <head.ref>` and `git merge --ff-only
   origin/<head.ref>` to ensure the worktree is at the latest PR HEAD.

This step runs on every tick — it is cheap (two local git commands + one
API call) and guards against session drift across wakeup cycles.

## Step 1: Resolve current HEAD and PR context

Read prior tick's state line from most recent assistant message (or
initialize fields if none). Increment `tick_count` by 1 in conversation
state line when **no** `state.json` (single-PR only). With `state.json`, do
**not** increment here — orchestrator's per-tick bump is sole increment.

```bash
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get") → `.head.sha`
```

If owner/repo/number are not yet known, extract them from the PR URL.
If `current_head` changed since last tick, reset `bugbot_down` to `false`
AND reset `bugbot_acknowledged_at` to `null` (new HEAD invalidates prior
down-detection state and starts a fresh 30-minute acknowledgement
budget for whatever bugbot review fires next).

Capture `number`, `head.sha` (= `current_head`), owner/repo, branch.

## Step 2: Branch on `phase`

### `phase == BUGBOT`

a. Fetch Cursor Bugbot reviews newest-first, walk back until first clean.
**Always go through `gh api --paginate --slurp` from the `Bash` tool, not
the MCP `pull_request_read` `get_reviews` method**: the MCP truncates at
~28-30 entries regardless of `page`/`perPage`, so on busy PRs the latest
cursor[bot] review for `current_head` lands past the cutoff and the MCP
walk reports "no review yet" while the data is in fact present (see
`SKILL.md` § Gotchas, "MCP `pull_request_read(...)` silently truncates").

   ```bash
   gh api 'repos/<owner>/<repo>/pulls/<N>/reviews?per_page=100' --paginate --slurp \
     | jq '[.[][] | select((.user.login | ascii_downcase) | contains("cursor"))]
            | sort_by(.submitted_at) | reverse'
   ```

   The result is the cursor[bot] review list newest-first across the full
   page set. Track dirty entries (review body contains `BUGBOT_REVIEW`
   markers with finding content); Fix protocol reads them back later this
   tick.

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
review on `current_head`. **Same MCP-truncation gotcha applies — use the
paginated `gh api` walk from `Bash`**:

   ```bash
   gh api 'repos/<owner>/<repo>/pulls/<N>/comments?per_page=100' --paginate --slurp \
     | jq '[.[][] | select((.user.login | ascii_downcase) | contains("cursor"))
                  | select(.in_reply_to_id == null)]
            | sort_by(.created_at) | reverse'
   ```

   Then narrow to threads where `is_outdated == false` AND `is_resolved
   == false` (when those flags are surfaced; the threads endpoint
   `pull_request_read(method="get_review_comments")` is still the canonical
   thread-shape source for `is_outdated`/`is_resolved` and is safe to use
   when the PR has fewer than ~25 threads — the cap also applies here, so
   on busy PRs cross-check thread state from the same paginated comments
   payload above by joining on `pull_request_review_id`).

c. Decide (five branches; match first whose predicate holds):
   - **No bugbot review yet, OR latest review's `commit_id` ≠
     `current_head` AND `bugbot_acknowledged_at` is unset OR
     `now - bugbot_acknowledged_at <= 30 min`:** Re-trigger bugbot (Step 3,
     skipped if the latest `bugbot run` comment already carries an
     `:eyes:`/`:+1:` reaction per duplicate-trigger gotcha), set
     `bugbot_clean_at = null`, reset `inline_lag_streak = 0`, schedule
     next wakeup, return.
   - **Latest review's `commit_id` ≠ `current_head` AND `bugbot_acknowledged_at`
     set AND `now - bugbot_acknowledged_at > 30 min`:** Bugbot effectively
     down on this commit even though the trigger was acknowledged. Set
     `bugbot_down = true`, `phase = BUGTEAM`, jump to Step 2 BUGTEAM same
     tick. The 30-minute budget is the empirical worst-case turnaround
     observed for Cursor Bugbot on large diffs; once exceeded with no
     surfaced review, the loop must move on rather than stall. Reset
     `bugbot_acknowledged_at` to `null` on the BUGTEAM jump (a fresh push
     during BUGTEAM will start a new acknowledgement window in Step 3).
   - **`commit_id == current_head` AND zero unaddressed inline AND review
     body clean:** Set `bugbot_clean_at = current_head`, reset
     `inline_lag_streak = 0`, `phase = BUGTEAM`. Continue BUGTEAM in same
     tick — back-to-back convergence requires bugteam on same HEAD
     before next wakeup.
   - **`commit_id == current_head` with unaddressed inline findings:**
     Apply **Fix protocol**. Reset `inline_lag_streak = 0`. With
     `state.json`: clean-coder teammate pushes, replies inline, writes
     `state.json`, goes idle; Step 3 on new HEAD runs after via
     orchestrator-spawned follow-up agent (§Fix result → general-purpose).
     No `state.json` (single-PR): spawn Agent (subagent_type: clean-coder) to implement → push → reply inline on each thread
     via `add_reply_to_pull_request_comment` MCP → Step 3 in same tick (see
     [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow) for
     full contract).
     Schedule next wakeup, return.
   - **`commit_id == current_head` AND review body findings AND inline
     API zero matching for `current_head`:** Transient API lag. Increment
     `inline_lag_streak`. `>= 3` → hard blocker; report and terminate with
     no loop pacing. Else Step 4 uses the BUGBOT inline-lag section of
     `../workflows/schedule-wakeup-loop.md` (`delaySeconds: 90`).

### `phase == BUGTEAM`

a. Run **bugteam** on current PR.

   - **`Skill` invokable**: invoke bugteam
     with `Skill`.

     ```
Skill({skill: "bugteam", args:
"https://github.com/<OWNER>/<REPO>/pull/<NUMBER>"})
     ```

   - **`Skill` not invokable** (typical delegated teammate): worker executes
     bugteam by reading [`../../bugteam/SKILL.md`](../../bugteam/SKILL.md). Same
     loop and gates; only harness steps differ.

b. **Re-resolve current HEAD (MANDATORY — never skip).** Bugteam may have
pushed commits during its run. `current_head` from Step 1 is stale:

   ```
   pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get") → `.head.sha`
   ```

   Capture `new_head`. Then check the most recent commit timestamp:

   ```
   list_commits(owner=OWNER, repo=REPO, sha="<branch>")
     → sort by `.commit.committer.date` descending → index 0 `.commit.committer.date`
   ```

   If the most recent commit timestamp is **less than 60 seconds ago**, the
   GitHub API may not have propagated it to review endpoints yet. Do not
   proceed with convergence-gates — schedule a 90s wakeup and return.
   Re-resolve HEAD next tick.

   If `new_head != current_head`, set `current_head = new_head`,
   `bugbot_clean_at = null`, `bugbot_down = false`. New commits invalidate
   bugbot's prior clean and down-detection state.

c. Inspect bugteam outcome. Reports `convergence (zero findings)` or list
of unfixed findings with file:line.

d. Decide based on post-bugteam state — order matters. Check
pushed-during-bugteam FIRST so convergence report against stale HEAD
never falsely terminates:
   - **Audit pushed this tick (`bugbot_clean_at` reset in step b):**
     Re-trigger bugbot same tick (Step 3) so new HEAD enters queue, `phase
     = BUGBOT`, schedule next wakeup, return.
   - **Convergence AND `bugbot_clean_at == current_head` (no push):**
     Back-to-back clean — necessary, not sufficient. Run **[convergence-gates.md](convergence-gates.md)** to clear all six gates: Copilot findings,
     Claude reviewer, mergeability, post-convergence Copilot request,
     thread resolution. Only when all six gates pass mark PR ready and
     **omit loop pacing** per **Convergence** of active pacing workflow.
   - **Convergence BUT `bugbot_clean_at != current_head` (no push):**
     `phase = BUGBOT`, schedule next wakeup, return.
   - **Findings without committed fixes:** spawn Agent (subagent_type: clean-coder) to implement fixes and push, then reply inline via `add_reply_to_pull_request_comment` MCP, following [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow).
     `phase = BUGBOT`, schedule next wakeup, return.

### `phase == COPILOT_WAIT`

Post-convergence Copilot re-check. Enters after gate (d) requests Copilot
review. Do **not** run bugteam here — that only happens after BUGBOT clean
on this HEAD.

a. Fetch latest Copilot review at `current_head` plus unaddressed inline
   comments. **Same MCP-truncation gotcha as BUGBOT — use `gh api
   --paginate --slurp` from `Bash`**:

   ```bash
   # Newest Copilot review at HEAD
   gh api 'repos/<owner>/<repo>/pulls/<N>/reviews?per_page=100' --paginate --slurp \
     | jq --arg sha '<current_head>' \
         '[.[][] | select((.user.login | ascii_downcase) | contains("copilot"))
                 | select(.commit_id == $sha)]
          | sort_by(.submitted_at) | reverse | .[0]'

   # Copilot inline comments from newest review
   gh api 'repos/<owner>/<repo>/pulls/<N>/comments?per_page=100' --paginate --slurp \
     | jq --arg review_id '<review_id>' \
         '[.[][] | select(.pull_request_review_id == ($review_id | tonumber))]'
   ```

b. Decide (three branches; match first whose predicate holds):

   - **Copilot review `state: APPROVED` at `current_head`:** Set
     `copilot_clean_at = current_head`. Record "Copilot APPROVED". Set
     `phase = BUGTEAM`. Continue to convergence-gates.md gate (b) in same
     tick — back-to-back convergence requires all gates on same HEAD.
   - **Copilot review dirty (CHANGES_REQUESTED or COMMENTED with findings)
     at `current_head`:** Apply **Fix protocol** — spawn Agent
     (subagent_type: clean-coder) to implement → push → reply inline on each
     thread via `add_reply_to_pull_request_comment` MCP. For body-only
     findings (no inline threads), post top-level review reply citing new
     HEAD SHA. Reset
     `bugbot_clean_at = null` AND `copilot_clean_at = null`. **Set
     `phase = BUGBOT`** (NOT COPILOT_WAIT) — every fix push requires a full
     back-to-back-clean cycle on the new HEAD. Schedule next wakeup, return.
   - **No Copilot review at `current_head` yet:** Increment
     `copilot_wait_count` (init 0 on COPILOT_WAIT entry; reset to 0 on
     every push and on every successful Copilot review). `>= 3` → hard
     blocker per [stop-conditions.md](stop-conditions.md). Otherwise
     schedule next wakeup (270s), return.

**Non-negotiable:** After any Copilot fix push, `phase` MUST route to
`BUGBOT`. Never cycle COPILOT_WAIT → fix → COPILOT_WAIT. The
back-to-back-clean guarantee (bugbot ∧ bugteam both clean on same HEAD
before gates re-open) only holds when every fix commit re-enters through
BUGBOT.

## Step 3: Re-trigger bugbot

Use the `add_issue_comment` MCP tool:

    add_issue_comment(owner="OWNER", repo="REPO", issue_number=NUMBER, body="bugbot run")

`bugbot run` is empirically the only re-trigger Cursor Bugbot recognizes;
alternative phrasings (`re-review`, `bugbot please`, etc.) silently no-op.

**Gotcha (duplicate `bugbot run` while review queued):** Skip Step 3 when
the latest `bugbot run` PR comment has an `:eyes:` or `:+1:` reaction; wait
for review or HEAD change before re-triggering.

**Bugbot-down detection:** After posting `bugbot run` via `add_issue_comment`,
capture the returned comment ID. Wait 15 seconds, then fetch comments via
`issue_read(method="get_comments", owner=OWNER, repo=REPO, issue_number=NUMBER)`,
select the comment whose `id` matches the captured ID, and check its
reactions. If the comment has zero reactions, bugbot did not
acknowledge — it is down. Set `bugbot_down = true`, `phase = BUGTEAM`, and
**jump to Step 2 BUGTEAM branch in this same tick** so bugteam runs
immediately against this HEAD without a wakeup cycle. If reactions are
present, bugbot acknowledged; record `bugbot_acknowledged_at = <now ISO
8601>` in the next-tick state line and proceed with normal pacing
(Step 4). The recorded timestamp arms the 30-minute wall-clock budget
checked in Step 2 BUGBOT (c) — once `now - bugbot_acknowledged_at > 30
min` with no review surfaced at `current_head`, the BUGBOT phase
escalates to bugbot-down even though the reaction was present, because
empirical Cursor Bugbot turnaround on this PR class never exceeds 30
minutes.

## Step 4: Loop pacing

**`ScheduleWakeup` field hints** (prefer [Pacing
workflow](#pacing-workflow)):

- `delaySeconds: 270` after bugbot re-trigger. Bugbot finishes in 1–4
  min; 270s stays under 5-min prompt-cache TTL with margin. Exception:
  BUGBOT inline-lag branch uses `delaySeconds: 90` (no re-trigger;
  awaiting GitHub inline API).
- `reason`: short sentence on what is awaited, including `phase` and
  `bugbot_clean_at` SHA.
- `prompt: "/pr-converge"`.

**On convergence:** apply **Convergence** section of
`../workflows/schedule-wakeup-loop.md` (omit wakeups).

## Bugteam execution

**Second audit** (BUGTEAM phase) is **always** **bugteam** skill: preflight,
CODE_RULES gate, **`code-quality-agent`** / **`clean-coder`** loop, audit
rubric, outcome shape, Step 2 BUGTEAM §(b)–(d) contract — all in
[`../../bugteam/SKILL.md`](../../bugteam/SKILL.md) plus `PROMPTS.md` / `EXAMPLES.md` /
`CONSTRAINTS.md`. Do not re-spec.

**pr-converge rule:** Prefer **`Skill({skill: "bugteam", args: "<PR URL or
args>"})`** wherever registry exposes `Skill`. When `Skill` not invokable
(typical delegated teammate), worker runs **bugteam** by loading
`../../bugteam/SKILL.md` from the same checkout. If bugteam cannot run, cancel the
convergence loop fully and report the issue to the user.
