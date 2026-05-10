# Bugteam — Evaluation Suite

Evaluation-driven iteration set for the `bugteam` skill, following [Anthropic — Agent Skills best practices: evaluation and iteration](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration).

## Methodology

Evals are split into two layers. Both layers run against the same trace but carry different failure semantics.

**Layer A — Ironclad invariants.** Order-and-presence rules that MUST hold on every run regardless of fixture, regardless of model choice, regardless of the exact number of loops taken. Citations use **section headings and companion files** (`SKILL.md`, `CONSTRAINTS.md`, `reference/*.md`) — not fragile line numbers — so layout edits to `SKILL.md` do not invalidate the contract. If an assertion fails, either the run diverged from the skill or the cited text is ambiguous and needs patching.

**Layer B — Fixture-dependent expectations.** The concrete tool trace predicted for a specific fixture (fixed PR state, canned audit XML, canned fix XML). Layer B is prediction — reality may diverge in small ways (extra `Bash("git rev-parse HEAD")` checkpoints the lead inserts for sanity; retry loops on transient failures; consolidated cleanup calls) without indicating a skill defect. Layer B failures trigger reconciliation, not auto-failure.

**Process note.** This document was drafted before running a real trace. Layer B predictions are labeled *predicted*, not *observed*. On the first real run, every Layer B prediction is reconciled against the observed trace and the diffs written back here — that reconciliation is Cycle 0 of the iteration protocol below.

## Ironclad invariants (Layer A, apply to every eval)

Each invariant cites the normative section or companion file it derives from. All spawns use `Agent(..., run_in_background=true)`. Invariants apply uniformly across all eval fixtures.

| # | Invariant | Citation |
|---|---|---|
| I-1 | `Bash` invoking `scripts/grant_project_claude_permissions.py` precedes the first audit `Agent` spawn. | `SKILL.md` § Step 0 |
| I-2 | `Bash` invoking `scripts/revoke_project_claude_permissions.py` runs exactly once per invocation on every exit path, after teardown. | `SKILL.md` § Step 5 |
| I-3 | Orchestration uses `Agent(..., run_in_background=true)` only — no `TeamCreate`, `TeamDelete`, `SendMessage`, or `Task` tool calls. | `SKILL.md` § Step 2; § Step 4 |
| I-4 | `Agent` calls are fresh per loop (`run_in_background=true`; new `name` each loop). | `CONSTRAINTS.md` — **Fresh subagent per loop** |
| I-5 | Every audit and fix spawn passes `model="opus"` (eleven category auditors `-a` through `-k`, the consolidator/validator `-validate`, and the fix subagent). | `SKILL.md` § AUDIT action (parallel auditors); § FIX action; `CONSTRAINTS.md` — **Opus 4.7 at xhigh effort for every auditor, validator, and fix subagent** |
| I-6 | Loop count ≤ 20 audits. 21st audit never fires. | `SKILL.md` YAML `description` (20-loop cap); § Step 3 (**Pre-audit** / **FIX** increment rules) |
| I-7 | Every audit loop runs the two-phase, twelve-teammate flow: phase 1 issues eleven parallel `Agent(..., run_in_background=true)` calls (one per A–K rubric, names `bugfind-pr<N>-loop<L>-a` through `-k`) in one assistant message; phase 2 issues one `Agent(name="bugfind-pr<N>-loop<L>-validate", run_in_background=true)` only after all eleven phase-1 notifications have arrived. There is no single-auditor mode and no loop-count gate. | `SKILL.md` § AUDIT action (**Phase 1** / **Phase 2**) |
| I-8 | Lead reads `.bugteam-pr<N>-loop<L>.outcomes.xml` with the `Read` tool after each audit, before the next action. | `SKILL.md` § AUDIT action |
| I-9 | Teardown sequence: `git worktree remove` each PR → `rmtree` `<run_temp_dir>` → Step 4.5 → revoke. | `SKILL.md` § Step 4; § Step 4.5; § Step 5 |
| I-10 | The bugfind subagent posts ONE per-loop review; the bugfix subagent posts fix replies. The lead's only PR-write action is the Step 4.5 description rewrite. | `CONSTRAINTS.md` — **Audit/fix comment posting** |

Any eval failing one or more Layer A invariants fails the run.

## Observation strategy

Evals run in a harness that intercepts the tool layer:

- A **mock tool layer** records each tool call with its arguments and returns synthetic responses matching the real tool's response shape. Nothing hits GitHub; no real teammates spawn.
- A **fixture repo** supplies deterministic git state and a mocked `gh` CLI that returns canned JSON for `pr view`, `pr diff`, and `api` calls.
- **Assertions** run against the recorded call list, not against real PR state.

The harness does not yet exist; this document defines its contract.

---

## Eval 1 — Smoke: background subagent spawns fire correctly

**Scenario.** PR exists; PR is a clean target with no unusual pre-conditions.

**Trigger.** `/bugteam`

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-8, I-9, I-10.

**Layer B predicted trace (smoke).**
1. `Bash("python .../grant_project_claude_permissions.py")` runs (Step 0).
2. `Agent(subagent_type="code-quality-agent", name="bugfind-pr...-loop1", run_in_background=true, model="opus", ...)` spawned for AUDIT.
3. Lead awaits background-completion notification, then `Read(".bugteam-pr42-loop1.outcomes.xml")`.
4. `Agent(subagent_type="clean-coder", name="bugfix-pr...-loop1", run_in_background=true, model="opus", ...)` spawned for FIX (if findings).
5. `Bash("python .../revoke_project_claude_permissions.py")` on exit.

**Pass criteria.**
- Non-zero `Agent(subagent_type="code-quality-agent", run_in_background=true)` and `Agent(subagent_type="clean-coder", run_in_background=true)` calls.

---

## Eval 2 — Refusal: missing PR, no upstream diff

**Scenario.** Current branch is `main` with no PR and no upstream difference.

**Layer B predicted trace.**
1. `Bash("gh pr view --json ...")` → non-zero exit.
2. `Bash("git merge-base HEAD origin/main")` → empty.
3. No grant script.

**Pass criteria.** Assistant message matches `No PR or upstream diff. /bugteam needs a target.`. Zero downstream tool calls.

---

## Eval 3 — Refusal: uncommitted changes in working tree

**Scenario.** Clean PR exists but `git status --porcelain` shows unstaged changes.

**Pass criteria.** Assistant message matches `Uncommitted changes detected. Stash, commit, or revert before /bugteam.`. Zero downstream tool calls.

---

## Eval 4 — Refusal: required subagent missing

**Scenario.** `code-quality-agent` is present in the available-agents list; `clean-coder` is not.

**Pass criteria.** Assistant message contains `Required subagent type clean-coder not installed.`. Zero grant script call, zero `Agent` spawns.

---

## Eval 5 — Happy path: converges in 2 loops

**Scenario.** PR #42 contains three P1 bugs all addressable by the mock fix subagent. Loop 1 audit returns 3 findings; loop 1 fix commits cleanly; loop 2 audit returns zero findings.

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-6, I-8, I-9, I-10.

**Layer B predicted trace.**

| # | Tool call | Source |
|---|---|---|
| 1 | `Bash("python .../scripts/grant_project_claude_permissions.py")` | `SKILL.md` § Step 0 |
| 2 | `Bash("gh pr view --json number,baseRefName,headRefName,url")` | `SKILL.md` § Step 1 |
| 3 | `Bash("git -C \"<run_temp_dir>/pr-42/worktree\" rev-parse HEAD")` → captures `starting_sha` | `SKILL.md` § Step 2 — **Loop state** block |
| 4 | `Bash("mkdir -p <run_temp_dir>/pr-42")` | `SKILL.md` § AUDIT action |
| 5 | `Bash("gh pr diff 42 -R ... > <run_temp_dir>/pr-42/loop-1.patch")` | `SKILL.md` § AUDIT action |
| 6 | Eleven parallel `Agent(subagent_type="code-quality-agent", name="bugfind-pr42-loop1-<letter>", run_in_background=true, model="opus", description=..., prompt=<audit XML for category <letter>>)` calls in one assistant message — letters `a` through `k` (phase 1) | `SKILL.md` § AUDIT action **Phase 1** |
| 7 | Lead awaits all eleven phase-1 background-completion notifications | `SKILL.md` § AUDIT action **Phase 1** |
| 8 | `Agent(subagent_type="code-quality-agent", name="bugfind-pr42-loop1-validate", run_in_background=true, model="opus", description=..., prompt=<validate XML; literal absolute paths to all 11 sibling XMLs>)` (phase 2) | `SKILL.md` § AUDIT action **Phase 2** |
| 8a | Lead awaits the consolidator/validator background-completion notification | `SKILL.md` § AUDIT action **Phase 2** |
| 8b | `Read(".bugteam-pr42-loop1.outcomes.xml")` — merged validator output | `SKILL.md` § AUDIT action **Phase 2** |
| 9 | `Agent(subagent_type="clean-coder", name="bugfix-pr42-loop1", run_in_background=true, model="opus", description=..., prompt=<fix XML loop 1>)` | `SKILL.md` § FIX action |
| 10 | Lead awaits background-completion notification | `SKILL.md` § FIX action |
| 11 | `Read(".bugteam-pr42-loop1.outcomes.xml")` — bugfix outcome XML | `SKILL.md` § FIX action |
| 12 | `Bash("git -C \"<run_temp_dir>/pr-42/worktree\" rev-parse HEAD")` → verify HEAD advanced | `SKILL.md` § FIX action (**Verify**) |
| 13 | `Bash("git -C \"<run_temp_dir>/pr-42/worktree\" fetch origin <branch>")` → fetch remote state | `SKILL.md` § FIX action (**Verify**) |
| 14 | `Bash("git -C \"<run_temp_dir>/pr-42/worktree\" rev-parse origin/<branch>")` → confirm matches HEAD | `SKILL.md` § FIX action (**Verify**) |
| 15 | `Bash("gh pr diff 42 -R ... > <run_temp_dir>/pr-42/loop-2.patch")` | `SKILL.md` § AUDIT action |
| 16 | Eleven parallel `Agent(name="bugfind-pr42-loop2-<letter>", ...)` calls in one assistant message (phase 1, loop 2) | `SKILL.md` § AUDIT action **Phase 1** |
| 17 | Lead awaits all eleven phase-1 notifications | `SKILL.md` § AUDIT action **Phase 1** |
| 17a | `Agent(name="bugfind-pr42-loop2-validate", ...)` (phase 2, loop 2) | `SKILL.md` § AUDIT action **Phase 2** |
| 17b | Lead awaits the consolidator/validator notification | `SKILL.md` § AUDIT action **Phase 2** |
| 18 | `Read(".bugteam-pr42-loop2.outcomes.xml")` — zero findings | `SKILL.md` § AUDIT action **Phase 2** |
| 19 | `Bash("git worktree remove \"<run_temp_dir>/pr-42/worktree\"")` | `SKILL.md` § Step 4 step 1 |
| 20 | `Bash("python -c \"...shutil.rmtree(r'<run_temp_dir>', ...)\"")` | `SKILL.md` § Step 4 step 2 (Windows-safe teardown) |
| 21 | `Bash("gh pr diff 42 -R ... > .bugteam-final.diff")` | `SKILL.md` § Step 4.5 step 1 |
| 22 | `Bash("gh pr view 42 -R ... --json body --jq .body > .bugteam-original-body.md")` | `SKILL.md` § Step 4.5 step 2 |
| 23 | `Agent(subagent_type="pr-description-writer", description=..., prompt=<brief>)` | `SKILL.md` § Step 4.5 |
| 24 | `Write(".bugteam-final-body.md", <returned body>)` | `SKILL.md` § Step 4.5 step 4 |
| 25 | `Bash("gh pr edit 42 -R ... --body-file .bugteam-final-body.md")` | `SKILL.md` § Step 4.5 step 4 |
| 26 | `Bash("rm .bugteam-final.diff .bugteam-original-body.md .bugteam-final-body.md")` | `SKILL.md` § Step 4.5 step 5 |
| 27 | `Bash("python .../scripts/revoke_project_claude_permissions.py")` | `SKILL.md` § Step 5 |

**Pass criteria.**
- All Layer A invariants hold.
- Exactly 22 `Agent(name="bugfind-pr42-loop[12]-[a..k]")` calls (eleven per loop in phase 1) plus exactly 2 `Agent(name="bugfind-pr42-loop[12]-validate")` calls (one per loop in phase 2), and exactly 1 `Agent(name="bugfix-pr42-loop1")` call.
- Final report contains `/bugteam exit: converged` and `Loops: 2`.

**Process check after first real run.** Compare the observed trace against steps 1–27. Common expected divergences that should not fail the eval:
- Extra `Bash("git rev-parse HEAD")` calls the lead inserts for bookkeeping.
- Consolidated `Bash` calls (step 25 may split into two or three calls).
- Extra `Read` calls when the lead re-reads an outcome XML to quote specific findings.
- Reordered but still-Layer-A-compliant cleanup sequencing.

Patch this table to match observation and annotate each correction.

---

## Eval 6 — Stuck path: fix subagent produces no commit

**Scenario.** Loop 1 audit finds 2 P1 bugs; the mock fix subagent reports both as `could_not_address` (no commit created).

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-6, I-8, I-9, I-10. I-6 trivially holds.

**Layer B predicted trace.** Identical to Eval 5 steps 1–12 with this divergence:
- Step 11 bugfix outcome XML marks every finding `status="could_not_address"`.
- Step 12 `Bash("git rev-parse HEAD")` returns the pre-fix SHA unchanged.
- Skill sets exit reason = `stuck`, skips loop 2, and falls through to `rmtree`.

**Pass criteria.**
- Loop count stops at 1.
- Final report contains `/bugteam exit: stuck` and names the two unresolved findings.
- Steps 19–26 fire despite the stuck exit — I-2 and I-9 enforce this.

---

## Eval 7 — Cap reached: 20 loops, no convergence

**Scenario.** Mock audit returns one P2 finding every loop. Mock fix subagent always commits but never clears the finding.

**Layer A invariants.** All of I-1 through I-10.

**Layer B predicted behavior.**
- Every loop (1–20) runs the two-phase, twelve-teammate flow: phase 1 issues eleven parallel `Agent(...)` calls in one assistant message — eleven opus category auditors named `bugfind-pr<N>-loop<L>-[a..k]`, each bound to one A–K rubric. After all eleven phase-1 notifications arrive, phase 2 issues one `Agent(name="bugfind-pr<N>-loop<L>-validate", run_in_background=true)`; lead awaits the consolidator/validator notification.
- Each loop produces one `Agent(name="bugfix-pr<N>-loop<L>", run_in_background=true)`.
- Exactly 20 audit phases, exactly 20 fix phases.
- Steps 19–26 from Eval 5 fire at teardown.

**Pass criteria.**
- I-6 holds: exactly 20 audit phases.
- I-7 holds: every loop emits eleven audit `Agent` calls in a single assistant message in phase 1, then one `-validate` `Agent` call in phase 2.
- Final report contains `/bugteam exit: cap reached` and the remaining bug count.

**Process check.** The distinct `Agent(name=...)` audit-call count is a prediction. On the first real run, record the exact count and rewrite the formula here.

---

## Eval 8 — Clean on first audit

**Scenario.** Loop 1 audit returns zero findings.

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-6, I-8, I-9, I-10.

**Layer B predicted trace.** Eval 5 steps 1–8 and 19–26 only — no FIX phase because zero findings means the skill exits the loop at `last_action == "audited"` and `last_findings.total == 0`.

**Pass criteria.**
- Exactly 12 `Agent(subagent_type="code-quality-agent", run_in_background=true)` calls in loop 1 (eleven category auditors `bugfind-pr<N>-loop1-[a..k]` in phase 1, one consolidator/validator `bugfind-pr<N>-loop1-validate` in phase 2), 0 fix agent spawns.
- The merged validator outcome XML records zero findings; the per-loop review POST carries body `## /bugteam loop 1 audit: 0P0 / 0P1 / 0P2 → clean`.
- Step 4.5 and Step 5 still fire.

---

## Eval 9 — Anchor fallback: finding outside diff

**Scenario.** Loop 1 audit returns 3 findings; 1 anchors to a line outside the captured diff.

**Layer A invariants.** Same as Eval 5.

**Layer B predicted subagent-side behavior** (observed via the recorded `gh api ... /reviews` POST payload in the bugfind subagent fixture).
- `comments[]` length in the POST body = 2 (anchored findings only).
- Review body contains a `### Findings without a diff anchor` section listing the third finding.
- Bugfix outcome XML marks all 3 findings with a `reply_comment_url`; the unanchored finding's `used_fallback="true"` and `finding_comment_url` equals the parent review URL.

**Pass criteria.** Confirmed in the fixture's canned teammate outcome XML; Layer A invariants hold on the lead side.

---

## Eval 10 — Review POST failure fallback

**Scenario.** The first `POST /pulls/42/reviews` call from the bugfind teammate returns HTTP 422.

**Layer B predicted teammate-side behavior.**
- Bugfind teammate retries via the issue-comments endpoint `POST /repos/.../issues/42/comments` with a single body carrying the review header and every finding inline.
- Every finding's outcome XML carries `used_fallback="true"` and the issue-comment URL as `finding_comment_url`.
- Cycle continues to the FIX action without aborting.

**Open item for the real run.** The issue-comments fallback shape is `jq -Rs | gh api .../issues/<number>/comments --input -` (`SKILL.md` § Step 2.5 **Review POST fails**; full narrative in `reference/github-pr-reviews.md` § **Review POST failure fallback**). Before running Eval 10 for real, confirm the teammate obeys this shape — the fixture must assert the endpoint path and the `--input -` pattern.

---

## Eval 11 — Hook-blocked fix commit

**Scenario.** Bugfix stages edits but `git commit` fails because a `pre-commit` hook returns non-zero.

**Layer B predicted behavior.**
- Bugfix teammate outcome XML marks every finding `status="hook_blocked"` with populated `<hook_output>`.
- Bugfix teammate posts `Hook blocked the fix commit: <one-line summary>` to each finding comment.
- Lead's `Bash("git rev-parse HEAD")` after fix detects no SHA change → exit reason `stuck`.
- Steps 19–26 from Eval 5 fire at teardown.

**Pass criteria.** Layer A I-2 and I-9 hold. Final report contains `/bugteam exit: stuck` and surfaces the hook_output summary.

---

## Eval 12 — `pr-description-writer` unavailable, `general-purpose` available

**Scenario.** The available-agents list does not include `pr-description-writer` but does include `general-purpose`.

**Layer B predicted trace.** Eval 5 steps 1–21 identical; step 22 becomes:

```
Agent(subagent_type="general-purpose", description="Rewrite PR 42 body from cumulative diff", prompt=<same brief>)
```

Steps 23–26 follow normally.

**Pass criteria.** Exactly 1 `Agent(subagent_type="general-purpose", ...)` call for the description rewrite. `gh pr edit` fires. Final report carries no Step 4.5 skip warning.

---

## Eval 13 — Neither PR-description agent available

**Scenario.** Neither `pr-description-writer` nor `general-purpose` appear in the available-agents list.

**Layer B predicted trace.** Eval 5 steps 1–21, then skip steps 22–24. Steps 25–26 still fire.

**Pass criteria.**
- Zero `Agent` calls for PR description rewriting.
- Zero `gh pr edit` calls.
- Final report carries the Step 4.5 skip warning.
- Layer A I-2 holds: revoke still fires.

---

## Eval 14 — Permissions revoke on error path

**Scenario.** Bugfind subagent completes but writes no outcomes XML (background subagent completes notification arrives with no file at the expected path).

**Layer B predicted trace.** Eval 5 steps 1–7, then:
- Lead awaits notification and calls `Read(".bugteam-pr42-loop1.outcomes.xml")` → file missing.
- Skill sets exit reason = `error: outcomes XML missing after bugfind loop 1`.
- Teardown (steps 19–26 from Eval 5) all fire.

**Pass criteria.** Final report surfaces the error and the loop number. Revoke fires despite the error.

---

## Iteration protocol

1. **Cycle 0 — Reconcile predictions with reality.** On the first real run, diff every Layer B predicted trace against the observed trace. Patch this file to match reality and annotate each correction with a reason.
2. **Baseline.** Run every eval with the skill unloaded. Record which cases the base model handles from memory versus which it gets wrong.
3. **Treatment.** Run every eval with the skill loaded. Layer A invariants must pass on every case. Layer B mismatches trigger Cycle 0 reconciliation.
4. **Regress on change.** Every edit to normative text in `SKILL.md`, `CONSTRAINTS.md`, `PROMPTS.md`, or `reference/*.md` sections that Layer A cites re-runs the full suite. A passing→failing transition on any Layer A invariant blocks the change. A Layer B mismatch after such an edit triggers a patch to the affected eval trace in the same commit.
5. **Extend on gotcha.** When the skill misfires in real use, add a new eval that reproduces the miss before patching the orchestration or companion files.

## Harness sketch (future work)

A minimal Python harness under `packages/claude-dev-env/skills/bugteam/evals/`:

- `harness.py` — loads a fixture, injects a mock tool layer that records calls and returns canned responses, invokes the lead with the trigger, collects the recorded trace, evaluates pass criteria.
- `fixtures/` — one subdirectory per eval with canned `gh` responses, canned audit XML, canned fix XML, and the expected trace JSON.
- `run_evals.py` — discovery + pass/fail reporting, exits non-zero on any failure for CI.
- `invariants.py` — the Layer A assertion bank, imported by every fixture.

## Open research items flagged during this pass

1. **GitHub REST review-POST payload shape.** Eval 9 and Eval 10 depend on the exact body shape of `POST /pulls/<number>/reviews`. The `jq -n --rawfile ... --argjson ... | gh api ... --input -` fence lives in `SKILL.md` § Step 2.5 (**Review POST**); expanded copy in `reference/github-pr-reviews.md` § **Per-loop review**. Before running Eval 9/10 for real, fetch the current GitHub REST reference to confirm the request schema (fields `commit_id`, `event`, `body`, `comments[]`) and the multi-line anchor `{path, start_line, start_side, line, side, body}` shape still apply. Record the confirmed version and URL here.
2. **Background subagent completion signal.** Real-run observation (loop 1 of eval run 2026-04-18) confirmed: background subagents self-terminate when their task is complete — the background-completion notification arrives and the lead reads the outcomes XML. No shutdown handshake required. `SKILL.md` § AUDIT / FIX actions document this flow. Layer A **I-4** encodes “fresh subagent per loop.”
3. **Model override redundancy.** `clean-coder` pins `model: opus` in its agent definition, while `code-quality-agent` currently uses `model: inherit`. The explicit `model="opus"` in every spawn is insurance against frontmatter drift; on the first real run, confirm the resolved model is `claude-opus-4-7` and that effort defaults to `xhigh` (Claude Code shows the active effort next to the spinner per the model-config docs). If a teammate's frontmatter ever pins a non-default `effort:` value, that frontmatter overrides the model default for that subagent (https://code.claude.com/docs/en/model-config — *"Frontmatter effort applies when that skill or subagent is active, overriding the session level but not the environment variable."*).
