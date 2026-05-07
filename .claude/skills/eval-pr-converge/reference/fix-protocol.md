# Fix protocol

Single-PR (no `state.json`): production edits run in main session via
`Agent` (`subagent_type: "eval-eval-clean-coder"`). Multi-PR (`state.json`):
eval-clean-coder teammate; orchestrator never edits inline. Hook handling
per [ground-rules.md](ground-rules.md).

**Multi-PR (`state.json`) teammate obligations** (plus TDD, commit, push):

- Replies inline on each addressed finding via
  `add_reply_to_pull_request_comment(owner=O, repo=R, pullNumber=N, commentId=<id>, body=…)`
  (what changed + commit identifier),
  matching §Audit result → fix worker step 4 — **before** writing
  `state.json` and going idle.
- Writes `last_action: "fix_pushed"`, `current_head: <new SHA>`,
  `round_1_clean_at: null`, `round: 1`, `status: "awaiting_bugbot"`,
  `last_updated` (ISO-8601 UTC) to `state.json` (per §Concurrency).
- Goes idle. Orchestrator spawns follow-up `general-purpose` agent for
  bugbot trigger and monitoring.

Orchestrator does not reply inline, trigger bugbot, or read repo source
files during fix phase in multi-PR mode.

**Single-PR (no `state.json`) — same gates, main session executor:**

- Read each referenced file:line.
- Write failing test first when finding has behavior to test. Pure doc /
  comment / naming nits with no behavior → straight to fix.
- **Pre-flight per-finding triage (mandatory before spawning the fix Agent).**
  For every finding in the input set, classify the obvious remediation against
  the live hook surface and the project rubric:
  - When the finding suggests editing or removing an existing comment, run
    `git diff origin/<base_branch> -- <file>` and check whether the comment
    on the current HEAD already differs from base. When it does, the
    no-deletion hook will block any revert — record the finding as `wontfix`
    with reason `comment-already-committed-on-head` and post a wontfix reply
    citing the AGENTS.md comment-edit exemption. Do NOT include this finding
    in the fix Agent's input set.
  - When the finding's category implies hook-enforced behavior, sanity-check
    the prediction against the latest gate output before forwarding it to the
    fix Agent.
  - **Fabricated-guideline citation (Copilot findings only).** When a Copilot
    finding cites a "project guideline" or "Custom guideline N" by name or
    number, verify the citation exists in `AGENTS.md`, `.cursor/BUGBOT.md`, or
    `~/.claude/docs/CODE_RULES.md` (case-insensitive substring match on rule
    name; for numbered guidelines, exact-number match). When the cited rule is
    not present in any rubric file, record the finding as `wontfix` with
    reason `fabricated-guideline-citation` and post a wontfix reply that
    quotes the cited rule and states "this guideline is not defined in
    AGENTS.md, .cursor/BUGBOT.md, or CODE_RULES.md; reopen with a citation
    that points to a defined rule." Do NOT include this finding in the fix
    Agent's input set.

**Copilot-rejection-round budget impact (eval mode).** When tracking the
`copilot_rejection_rounds` budget under `BUGTEAM_EVAL_MODE=1`, a Copilot review
counts as a rejection round **only when at least one finding in the review
survives triage with a status other than `wontfix-no-cycle`**. The
`wontfix-no-cycle` statuses are: `fabricated-guideline-citation`,
`comment-already-committed-on-head`, and any finding whose category is purely
docstring/textual with no behavior to test (the existing converged-no-cycle
class). A review composed entirely of `wontfix-no-cycle` findings receives
its wontfix replies but does not increment `copilot_rejection_rounds`.
Reviews with mixed actionable + `wontfix-no-cycle` findings count as one
round (the actionable findings drive the next fix loop).
- **Implement** via `Agent` (`subagent_type: "eval-eval-clean-coder"`).
  Full-stop if `Agent` is unavailable.
- **Per-finding commits.** The fix Agent applies one finding at a time, each
  in its own commit:
  ```bash
git add <files-for-finding-K> && git commit -m "fix(review): <finding_id> — <one-line>"
  ```
  When a per-finding commit is hook-blocked, capture stderr, run
  `git reset --hard HEAD` to discard staged changes for that finding only,
  mark the finding `hook_blocked`, and continue to the next finding. The
  remaining findings in the input set are NOT affected by the hook block on
  the prior finding.
- **Narrow scope.** Fix only the exact defect at the specified file:line. No structural refactoring, no inlining helpers.
- **Scope-lock:** Change the exact line(s) specified in the finding. Do not
  modify any code outside the finding's file:line range. Do not refactor,
  rename, or restructure code beyond the minimal change needed. Every scope
  creep edit (changing unrelated guards, log levels, or search parameters)
  becomes a self-inflicted regression that requires its own fix loop.
- **Preserve helpers.** Do not remove or inline existing helper functions unless the finding explicitly names them.
**Pre-commit gate:** honor hooks; full-stop on bypass except for the
per-finding hook_blocked path above.
- Push every successful per-finding commit at the end of the round:
  ```bash
git push origin <BRANCH>
  ```
**Pre-push gate:** honor hooks; full-stop on bypass. Capture new HEAD
only after both gates pass; set `current_head`, `bugbot_clean_at = null`.
- **Post-fix verification (lead).** For every per-finding commit, grep the
  edited file for the substring or regex that proves the change landed
  (the new function name, the new constant, the structural rewrite). When
  grep does not find evidence the change is on disk, downgrade the finding
  to `could_not_address` for the next round and log the divergence — the
  fix Agent's prose report is not ground truth.
- Reply inline on each addressed comment thread using `--body-file` (per
  gh-body-file rule):
  ```bash
python "${CLAUDE_SKILL_DIR}/scripts/reply_to_inline_comment.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER> \
--comment-id <COMMENT_ID> --body-file <path/to/reply.md>
  ```
- **After pushing a fix, always run Step 3 (`bugbot run`) in the same
  tick** regardless of phase. New commit **resets full convergence cycle**:
  prior bugbot clean and prior eval-bugteam clean on older SHA do **not**
  count toward convergence on new `HEAD`. Must re-obtain bugbot CLEAN on
  `current_head`, then eval-bugteam CLEAN on same `HEAD` with no
  intervening push. Re-triggering in same tick saves a wakeup cycle vs
  deferring Step 3.
