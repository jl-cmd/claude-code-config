# Examples

Worked examples for `cm-pr-converge`. Read on demand when a tick's
classification is novel or ambiguous against the in-skill rules. Cross-refs
into `SKILL.md` use `§Section name` notation.

<example> User: `/pr-converge` Claude: [PR context + one tick bugbot/bugteam
work; Step 4 per loaded pacing workflow — default loop until convergence or
stop]
</example>

<example> User: `/loop /pr-converge` Claude: [same per-tick work and Step 4 as
bare `/pr-converge` — harness wrapper only when host routes wakeups through
`/loop`]
</example>

<example> BUGBOT tick, latest bugbot review against older commit. Claude:
[posts `bugbot run`, sets `bugbot_clean_at = null`, Step 4 per
`workflows/schedule-wakeup-loop.md` (e.g. 270s wakeup), returns]
</example>

<example> BUGBOT tick, bugbot has 2 unaddressed findings on HEAD. Claude:
[TDD-fixes both, one commit, pushes, replies inline on both threads, posts
`bugbot run`, Step 4 at 270s, returns]
</example>

<example> BUGBOT tick, bugbot clean against HEAD. Claude: [sets
`bugbot_clean_at = HEAD`, `phase = BUGTEAM`, runs `Skill({skill: "bugteam",
...})` in same tick — bugteam Path routing picks Path A vs B internally]
</example>

<example> BUGTEAM phase, bugteam reports convergence and `bugbot_clean_at
== current_head`. Claude: [runs `gh pr ready <NUMBER>`, reports "PR
converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for
review", applies **Convergence** from active pacing workflow]
</example>

<example> BUGTEAM phase, bugteam pushed fix commit during run. Claude:
[re-resolves HEAD, sets `bugbot_clean_at = null`, posts `bugbot run` in
same tick, `phase = BUGBOT`, Step 4 at 270s]
</example>

<example> BUGBOT tick, review body says "found 3 potential issues" against
HEAD but inline API returns zero matching for `current_head`. Claude:
[increments `inline_lag_streak` to 1, Step 4 inline-lag rules (60s
`ScheduleWakeup` vs AHK cadence), returns]
</example>

<example> BUGTEAM tick with no agent teams: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
unset; bugteam Path B applies inside `Skill`. Claude: [invokes bugteam;
bugteam runs Path B per `bugteam/SKILL.md` +
`bugteam/reference/workflow-path-b-task-harness.md`; applies Step 2
§(b)–(d) unchanged]
</example>

<example> Back-to-back clean reached, but `mergeStateStatus: DIRTY` (base
advanced, merge conflicts). Claude: [runs §Convergence gates (b); does NOT
mark ready; invokes `rebase` skill per `../../rebase/SKILL.md` Phase 1–4;
after force-with-lease push, resets `bugbot_clean_at = null`,
`copilot_clean_at = null`, `merge_state_status = null`, `phase = BUGBOT`,
posts `bugbot run` on new HEAD, schedules next wakeup]
</example>

<example> Back-to-back clean, mergeability CLEAN, Copilot review at
`current_head` `state == "CHANGES_REQUESTED"` with two unaddressed inline
findings. Claude: [runs §Convergence gates (a); applies Fix protocol (TDD
test → fix → push → reply inline both threads), resets `bugbot_clean_at`
and `copilot_clean_at` null, `phase = BUGBOT`, posts `bugbot run` on new
HEAD, schedules next wakeup]
</example>

<example> Back-to-back clean, mergeability CLEAN, no Copilot review on
`current_head`. Claude requests Copilot via `request_copilot_review.py`,
waits one tick. Next tick: Copilot review `state: APPROVED`. Claude: [sets
`copilot_clean_at = current_head`; runs `mark_pr_ready.py`; reports "PR
#N converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>,
mergeStateStatus CLEAN, copilot CLEAN; marked ready for review"]
</example>

<example> Back-to-back clean, mergeability CLEAN, post-convergence Copilot
review returned `state: CHANGES_REQUESTED` with inline findings on
`current_head`. Claude: [still marks PR ready (four-gate rule allows
convergence when follow-up captures Copilot findings); builds findings
checklist from `fetch_copilot_inline_comments.py`; runs
`open_followup_copilot_pr.py` off `current_head` (branch
`chore/copilot-followup-<NUMBER>-<short_sha>`, title `chore: address
Copilot findings from PR #<NUMBER>`); reports both URLs; queues
`/pr-converge` on new PR for user]
</example>
