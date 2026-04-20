---
name: qbug
description: >-
  Minimized alternate to /bugteam: the lead spawns ONE subagent (not a team)
  that runs the audit → fix → commit → push cycle on the open PR until
  convergence or stuck. Same CODE_RULES gate and A–J category rubric as
  /bugteam, same per-loop PR review shape, but no TeamCreate, no teammates,
  no per-loop clean-room, and no loop cap. Triggers: '/qbug', 'quick bug
  audit', 'solo bug audit', 'bugteam without a team'.
---

# qbug

**Core principle:** The /bugteam workflow, driven by ONE subagent. The lead spawns a single `clean-coder` via the Agent tool (no `TeamCreate`, no teammates), hands it the PR scope and audit rubric, and the subagent loops audit → fix → commit → push until convergence or stuck. The trade: no per-loop clean-room (the subagent's context carries across loops). The gain: no agent-teams feature requirement, no teammate coordination, no loop cap.

Reuses /bugteam's shared pieces by path:

- Pre-flight: `packages/claude-dev-env/skills/bugteam/scripts/bugteam_preflight.py`
- Code-rules gate: `packages/claude-dev-env/skills/bugteam/scripts/bugteam_code_rules_gate.py`
- Bug category rubric A–J: [`bugteam/PROMPTS.md`](../bugteam/PROMPTS.md#audit-spawn-prompt-xml-bugfind-teammate)
- PR comment lifecycle shape: [`bugteam/SKILL.md`](../bugteam/SKILL.md#step-25-pr-comments-one-review-per-loop)

## When this skill applies

`/qbug` once authorizes the full cycle (no loop cap — runs until `converged` or `stuck`; user can interrupt at any time).

Refusals — first match wins; respond with the quoted line exactly and stop:

- **No PR or upstream diff.** `No PR or upstream diff. /qbug needs a target.`
- **Dirty tree.** `Uncommitted changes detected. Stash, commit, or revert before /qbug.`
- **Missing subagent.** Before Step 2, confirm `clean-coder` exists. Else: `Required subagent type clean-coder not installed. /qbug needs clean-coder available.`

## Progress checklist

```
[ ] Step 0: pre-flight clean
[ ] Step 1: PR scope resolved
[ ] Step 2: subagent cycle complete (converged | stuck | error)
[ ] Step 3: PR description refreshed
[ ] Step 4: final report printed
```

## Step 0: Pre-flight

```bash
python packages/claude-dev-env/skills/bugteam/scripts/bugteam_preflight.py
```

Non-zero → fix before continuing. `BUGTEAM_PREFLIGHT_SKIP=1` is emergency only. `--pre-commit` when `.pre-commit-config.yaml` exists.

## Step 1: Resolve PR scope (lead)

1. `gh pr view --json number,baseRefName,headRefName,url`
2. Else `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`
3. Else refuse per § When this skill applies.

Capture: `owner/repo`, `baseRefName`, `headRefName`, PR `number`, `url`, `starting_sha = git rev-parse HEAD`.

## Step 2: Spawn the single subagent

Lead calls `Agent`:

```
Agent(
  subagent_type="clean-coder",
  description="qbug audit/fix cycle for PR <number>",
  prompt="<cycle XML; see § Subagent cycle prompt>",
  run_in_background=false
)
```

One subagent, not a team. No `TeamCreate`, no `team_name`, no teammate shutdown protocol. The subagent returns when it has exited the cycle (converged, stuck, or error).

## Subagent cycle prompt

The subagent receives the PR scope plus the instructions below. It loops internally — the lead does not re-invoke between loops.

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head ref</branch>
  <base_branch>base ref</base_branch>
  <pr_url>url</pr_url>
  <starting_sha>starting_sha</starting_sha>
</context>

<cycle>
  Maintain inline:
    loop_count = 0
    last_action = "fresh"           # fresh | audited | fixed
    last_findings = {p0, p1, p2, total}
    loop_comment_index = {}
    audit_log = []

  Loop until exit (no cap):
    1. Dispatch:
       - last_action == "audited" and last_findings.total == 0 → exit "converged"
       - last_action == "fixed" and `git rev-parse HEAD` unchanged since pre-FIX → exit "stuck"
       - last_action in {"fresh", "fixed"} → pre-audit, then AUDIT
       - last_action == "audited" and last_findings.total > 0 → FIX

    2. Pre-audit (before every AUDIT):
       `python packages/claude-dev-env/skills/bugteam/scripts/bugteam_code_rules_gate.py --base origin/<baseRefName>`
       Non-zero → fix the reported violations inline, re-run the same command.
       After 3 failed rounds → exit "error: code rules gate failed pre-audit".
       After exit 0: loop_count += 1.

    3. AUDIT:
       mkdir -p /tmp/qbug-<number>
       gh pr diff <number> -R <owner>/<repo> > /tmp/qbug-<number>/loop-<N>.patch

       - Read the patch.
       - Audit only added/modified lines against categories A–J from
         packages/claude-dev-env/skills/bugteam/PROMPTS.md.
       - Assign each finding loop<N>-<K> (1-based). Partition into
         anchored (line in diff) and unanchored.
       - Use the Step 2.5 payload shape from bugteam/SKILL.md:
         write review body + per-finding bodies to temp files,
         jq --rawfile / -Rs, pipe to
         `gh api repos/<owner>/<repo>/pulls/<number>/reviews -X POST --input -`.
         Review body: `## /qbug loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2`.
       - Review POST fails → issue-comment fallback on
         `/issues/<number>/comments` with full body; mark all findings
         used_fallback=true.
       - Harvest html_url for parent review and each child comment;
         populate loop_comment_index.
       - last_action = "audited"; last_findings = counts.
       - Append `<N> audit: <P0>P0 / <P1>P1 / <P2>P2` to audit_log.

    4. FIX:
       - Apply each fix: read the file before editing; preserve existing
         comments on untouched lines; add type hints on touched signatures.
       - `python -m py_compile` (or language-equivalent) on each modified file.
       - `git add <path>` by explicit path for every modified file.
       - Single commit summarizing the fixed findings. Let hooks run.
         Hook-blocked → capture stderr, mark every finding hook_blocked,
         do NOT retry this loop.
       - `git push` (plain fast-forward).
       - For each finding, post one reply to
         loop_comment_index[finding_id].finding_comment_id using the
         Step 2.5 reply shape: `Fixed in <short_sha>` /
         `Could not address this loop: <reason>` /
         `Hook blocked the fix commit: <summary>`.
       - last_action = "fixed". Append
         `<N> fix: <sha> — <fixed>/<could_not_address>/<hook_blocked>`
         to audit_log.

    5. Loop to step 1.
</cycle>

<constraints>
  - Modify only files in the PR diff's scope.
  - Linear branch, fast-forward push only; one commit per FIX action.
  - Preserve existing comments on lines you do not modify.
  - Type hints on every signature you touch.
  - Read each file before editing.
  - No TeamCreate, no Agent calls, no spawning other subagents from within
    this subagent — this is the lone worker for the whole cycle.
</constraints>

<output_format>
  Return to the lead with:
    - exit_reason: converged | stuck | error: <detail>
    - loop_count
    - final_commit_sha (git rev-parse HEAD)
    - audit_log (ordered list of per-loop lines)
    - unresolved (only when stuck): [{file, line, severity, title, reason}]
</output_format>
```

## Step 3: PR description refresh (lead)

Delegate body composition to the `pr-description-writer` agent (the mandatory-pr-description hook requires it for `gh pr edit` to succeed). Feed it the final PR diff and the original body. Apply via `gh pr edit <number> -R <owner>/<repo> --body-file .qbug-final-body.md`.

On error exit paths: best-effort; log the failure in the final report and continue.

## Step 4: Final report (lead)

```
/qbug exit: <converged | stuck | error>
Loops: <loop_count>
Starting commit: <starting_sha7>
Final commit: <current_HEAD_sha7>
Net change: <files> files, +<add>/-<del>

Loop log:
  1 audit: 2P0 / 1P1 / 0P2
  1 fix: a1b2c3d — 3 fixed, 0 skipped
  2 audit: 0P0 / 0P1 / 0P2 → converged
```

- `stuck` → list the unresolved findings with `file:line` and reason.
- `error` → error detail + loop number where it occurred.

Delete `/tmp/qbug-<number>/` and any `.qbug-*.md` temp files.

## Constraints

- **One subagent, not a team.** Lead spawns a single `clean-coder` via the Agent tool. No `TeamCreate`. The subagent does not spawn further subagents.
- **No loop cap.** Cycle runs until `converged`, `stuck`, or `error`. User can interrupt.
- **Code rules gate before every AUDIT.** Same `validate_content` logic as /bugteam.
- **One commit per FIX action.** Linear branch, fast-forward push only.
- **Categories A–J.** Same rubric as [`bugteam/PROMPTS.md`](../bugteam/PROMPTS.md).
- **One review per loop.** Anchored findings as `comments[]`; unanchored listed under "Findings without a diff anchor" in the review body.
- **PR description rewrite on every exit**, same as /bugteam Step 4.5.
- **Temp file cleanup on every exit path.**
- **No per-loop clean-room.** The single subagent's context accumulates across loops — that is the explicit trade vs /bugteam. For convergence-critical audits where bias isolation matters, use /bugteam.

## Examples

<example>
User: `/qbug`
Lead: [preflight, resolves PR #42, spawns ONE clean-coder subagent with the cycle prompt]
Subagent: [runs loops internally, returns]

`Loop 1 audit: 1P0 / 2P1 / 0P2`
`Loop 1 fix: commit a1b2c3d (3 files, +18/-7) — 3 fixed, 0 skipped`
`Loop 2 audit: 0P0 / 1P1 / 0P2`
`Loop 2 fix: commit e4f5g6h (1 file, +5/-2) — 1 fixed, 0 skipped`
`Loop 3 audit: 0P0 / 0P1 / 0P2 → converged`

`/qbug exit: converged`
`Loops: 3`
`Starting commit: 9d8c7b6`
`Final commit: e4f5g6h`
`Net change: 4 files, +23/-9`
</example>

<example>
User: `/qbug`
Subagent: [loop 4 fix produces no commit despite findings]

`Loop 4 fix: no changes — could not address remaining 2 findings`
`/qbug exit: stuck`
`Unresolved: src/cache.py:88 (P0 race condition); src/parser.py:44 (P1 unbound reference)`
</example>

<example>
User: `/qbug` (no PR or upstream diff)
Lead: `No PR or upstream diff. /qbug needs a target.`
</example>

## Why this design

`/bugteam` solves the anchoring-bias problem by spawning a fresh auditor every loop. The cost is complexity: the agent-teams feature, team creation, outcome XML handoffs, teammate shutdown protocols, a 10-loop safety cap.

`/qbug` collapses that into one subagent. The lead spawns a single `clean-coder` that runs the full audit-fix-loop to completion. No team machinery, no cap — the cycle converges naturally, gets stuck on unfixable findings, or errors on the gate. When convergence matters more than bias isolation, or when agent teams aren't available, `/qbug` is the cheaper path.
