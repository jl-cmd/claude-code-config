---
name: qbug
description: >-
  Minimized alternate to /bugteam: the lead agent itself runs audit → fix →
  commit → push loops on the open PR, in its own context. Same CODE_RULES
  gate and A–J category rubric as /bugteam, same per-loop PR review shape,
  but no TeamCreate, no teammates, no clean-room isolation. Triggers:
  '/qbug', 'quick bug audit', 'solo bug audit', 'bugteam without a team'.
---

# qbug

**Core principle:** The /bugteam workflow, done by the lead agent. Audit → fix → commit → push, looped until zero findings or a safety cap. The trade: no per-loop clean-room (the lead's context carries across loops). The gain: no agent-teams feature requirement, no teammate coordination, fewer moving parts.

Reuses /bugteam's shared pieces by path:

- Pre-flight: `packages/claude-dev-env/skills/bugteam/scripts/bugteam_preflight.py`
- Code-rules gate: `packages/claude-dev-env/skills/bugteam/scripts/bugteam_code_rules_gate.py`
- Bug category rubric A–J: [`bugteam/PROMPTS.md`](../bugteam/PROMPTS.md#audit-spawn-prompt-xml-bugfind-teammate)
- PR comment lifecycle shape: [`bugteam/SKILL.md`](../bugteam/SKILL.md#step-25-pr-comments-one-review-per-loop)

## When this skill applies

`/qbug` once authorizes the full cycle (up to 5 audit+fix loops).

Refusals — first match wins; respond with the quoted line exactly and stop:

- **No PR or upstream diff.** `No PR or upstream diff. /qbug needs a target.`
- **Dirty tree.** `Uncommitted changes detected. Stash, commit, or revert before /qbug.`

## Progress checklist

```
[ ] Step 0: pre-flight clean
[ ] Step 1: PR scope resolved
[ ] Step 2: cycle complete (converged | cap reached | stuck | error)
[ ] Step 3: PR description refreshed
[ ] Step 4: final report printed
```

## Step 0: Pre-flight

```bash
python packages/claude-dev-env/skills/bugteam/scripts/bugteam_preflight.py
```

Non-zero → fix before continuing. `BUGTEAM_PREFLIGHT_SKIP=1` is emergency only. `--pre-commit` when `.pre-commit-config.yaml` exists.

## Step 1: Resolve PR scope

1. `gh pr view --json number,baseRefName,headRefName,url`
2. Else `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`
3. Else refuse per § When this skill applies.

Keep: `owner/repo`, `baseRefName`, `headRefName`, PR `number`, `url`, `starting_sha = git rev-parse HEAD`.

## Step 2: The cycle

Maintain inline (no team state file):

```
loop_count = 0
last_action = "fresh"           # fresh | audited | fixed
last_findings = {p0: 0, p1: 0, p2: 0, total: 0}
loop_comment_index = {}         # finding_id -> {finding_comment_id, finding_comment_url, used_fallback, fix_status}
audit_log = []                  # per-loop lines for the final report
```

Loop:

1. **Dispatch:**
   - `last_action == "audited"` and `last_findings.total == 0` → exit `converged`
   - `last_action == "fixed"` and `git rev-parse HEAD` unchanged since pre-FIX → exit `stuck`
   - `last_action in {"fresh", "fixed"}` → pre-audit, then AUDIT
   - `last_action == "audited"` and `last_findings.total > 0` → FIX

2. **Pre-audit** (before every AUDIT):

   ```bash
   python packages/claude-dev-env/skills/bugteam/scripts/bugteam_code_rules_gate.py --base origin/<baseRefName>
   ```

   Non-zero → fix the reported violations inline (same session), re-run the same command. After 3 failed rounds → exit `error: code rules gate failed pre-audit`. After exit **0**: `loop_count += 1`; if `loop_count > 5` → exit `cap reached`.

3. **AUDIT** (done by the lead agent, in this session):

   ```bash
   mkdir -p /tmp/qbug-<number>
   gh pr diff <number> -R <owner>/<repo> > /tmp/qbug-<number>/loop-<N>.patch
   ```

   - Read the patch.
   - Audit only the added/modified lines against categories A–J from [`bugteam/PROMPTS.md`](../bugteam/PROMPTS.md).
   - Assign each finding `loop<N>-<K>` (1-based). Partition into anchored (line in diff) and unanchored.
   - Use the [`bugteam/SKILL.md` Step 2.5](../bugteam/SKILL.md#step-25-pr-comments-one-review-per-loop) payload shape: write review body + per-finding bodies to temp files, `jq --rawfile` / `-Rs`, pipe to `gh api repos/<owner>/<repo>/pulls/<number>/reviews -X POST --input -`. Review body: `## /qbug loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2` (substitute /qbug for /bugteam).
   - Review POST fails → issue-comment fallback: `gh api repos/<owner>/<repo>/issues/<number>/comments -X POST --input -` with full body; mark all findings `used_fallback=true`.
   - Harvest `html_url` for the parent review and each child comment; populate `loop_comment_index`.
   - `last_action = "audited"`; `last_findings` = the {p0,p1,p2,total} counts. Append `<N> audit: <P0>P0 / <P1>P1 / <P2>P2` to `audit_log`.

4. **FIX** (done by the lead agent, in this session):

   - Apply each fix: read the file before editing; preserve existing comments on untouched lines; add type hints on touched signatures.
   - Run `python -m py_compile` (or language-equivalent) on every modified file.
   - `git add <path>` by explicit path for every modified file (never `-A` / `.`).
   - Single commit summarizing the fixed findings. Let hooks run. If a hook blocks, capture its stderr, mark every finding `hook_blocked`, do NOT retry this loop.
   - `git push` (plain fast-forward).
   - For each finding, post one reply to `loop_comment_index[finding_id].finding_comment_id` using the [Step 2.5 reply shape](../bugteam/SKILL.md#step-25-pr-comments-one-review-per-loop): `Fixed in <short_sha>` / `Could not address this loop: <reason>` / `Hook blocked the fix commit: <summary>`.
   - `last_action = "fixed"`. Append `<N> fix: <sha> — <fixed>/<could_not_address>/<hook_blocked>` to `audit_log`.

5. Loop to step 1.

## Step 3: PR description refresh

Delegate body composition to the `pr-description-writer` agent (the mandatory-pr-description hook requires it for `gh pr edit` to succeed). Feed it the final PR diff and the original body. Apply via `gh pr edit <number> -R <owner>/<repo> --body-file .qbug-final-body.md`.

On error exit paths: best-effort; log the failure in the final report and continue.

## Step 4: Final report

```
/qbug exit: <converged | cap reached | stuck | error>
Loops: <loop_count>
Starting commit: <starting_sha7>
Final commit: <current_HEAD_sha7>
Net change: <files> files, +<add>/-<del>

Loop log:
  1 audit: 2P0 / 1P1 / 0P2
  1 fix: a1b2c3d — 3 fixed, 0 skipped
  2 audit: 0P0 / 0P1 / 0P2 → converged
```

- `cap reached` → suggest `/bugteam` for deeper team-based loops (clean-room per loop).
- `stuck` → list the unresolved findings with `file:line` and reason.
- `error` → error detail + loop number where it occurred.

Delete `/tmp/qbug-<number>/` and any `.qbug-*.md` temp files.

## Constraints

- **Single-agent, in-session.** Lead does audit and fix itself. No `TeamCreate`, no `Agent(subagent_type=...)`, no teammates.
- **5-loop hard cap** (vs /bugteam's 10). Counted as AUDIT completions.
- **Code rules gate before every AUDIT.** Same `validate_content` logic as /bugteam.
- **One commit per FIX action.** Linear branch, fast-forward push only.
- **Categories A–J.** Same rubric as [`bugteam/PROMPTS.md`](../bugteam/PROMPTS.md).
- **One review per loop.** Anchored findings as `comments[]`; unanchored listed under "Findings without a diff anchor" in the review body.
- **PR description rewrite on every exit**, same as /bugteam Step 4.5.
- **Temp file cleanup on every exit path.**
- **No clean-room guarantee.** Prior audits' context persists in this session — that is the explicit trade vs /bugteam. For convergence-critical audits where bias matters, use /bugteam.

## Examples

<example>
User: `/qbug`
Lead: [preflight, resolves PR #42, runs loop]

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
Lead: [loop 4 fix produces no commit despite findings]

`Loop 4 fix: no changes — could not address remaining 2 findings`
`/qbug exit: stuck`
`Unresolved: src/cache.py:88 (P0 race condition); src/parser.py:44 (P1 unbound reference)`
</example>

<example>
User: `/qbug` (no PR or upstream diff)
Lead: `No PR or upstream diff. /qbug needs a target.`
</example>

## Why this design

`/bugteam` solves the anchoring-bias problem by spawning a fresh auditor every loop. The cost is complexity: the agent-teams feature, team creation, outcome XML handoffs, teammate shutdown protocols. For PRs where the lead's context is neutral enough (the session hasn't already anchored on specific files or bug shapes), the audit-fix-loop by the lead itself produces the same converged state with much less orchestration.

`/qbug` is that path. When convergence matters more than bias isolation, or when agent teams aren't available, `/qbug` runs the same loop inline — gate, audit, fix, commit, push, reply, repeat.
