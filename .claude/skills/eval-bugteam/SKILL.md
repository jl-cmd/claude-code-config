---
name: bugteam
description: >-
  Open pull request audit–fix until convergence: CODE_RULES gate, clean-room
  audit (`eval-code-quality-agent`, opus) and fix (`eval-clean-coder`, opus), per-loop
  GitHub reviews, 10-audit cap; grant then revoke `.claude/**`. Spawns
  background subagents (`Agent(..., run_in_background=true)`). Triggers: '/eval-bugteam', 'run
  the bug team', 'auto-fix the PR until clean', 'loop audit and fix'.
---

# Bugteam

**Core principle:** Audit–fix until convergence. **Bugfind:**
`eval-code-quality-agent`, fresh context each loop. **Bugfix:** `eval-clean-coder`. Hard
cap: 10 audit loops. Grant `.claude/**` at start, revoke always at end.

Both audit and fix roles run as background subagents
(`Agent(..., run_in_background=true)`). Verbatim doc quotes and URLs:
[`sources.md`](sources.md).

## Contents

Orchestration lives here; companion files hold prompts, invariants, examples,
citations, and domain reference notes. Scan this list before a partial read.

- When this skill applies — refusal cases and trigger conditions
- Utility scripts — pre-flight (`scripts/`, executed not inlined)
- Pre-audit gate — `validate_content` before each AUDIT
- The Process — checklist + Steps 0–6
  - Step 0 — Grant project permissions
  - Step 1 — Resolve PR scope
  - Step 2 — Loop state
  - Step 2.5 — PR comment lifecycle (per-loop review + fix replies)
  - Step 3 — Cycle (AUDIT ↔ FIX, exits)
  - Step 4 — Teardown + clean tree
  - Step 4.5 — PR body via `eval-pr-description-writer`
  - Step 5 — Revoke permissions
  - Step 6 — Final report
- [`PROMPTS.md`](PROMPTS.md) — spawn XML, categories A–J, outcome schemas
- [`EXAMPLES.md`](EXAMPLES.md) — exit scenarios
- [`CONSTRAINTS.md`](CONSTRAINTS.md) — invariants and design rationale
- [`sources.md`](sources.md) — doc URLs and verbatim quotes
- [`reference/README.md`](reference/README.md) — expanded prose by topic
  (design, team setup, GitHub reviews, cycle, teardown)

## When this skill applies

`/eval-bugteam` once authorizes the full cycle (up to 10 audits + fixes).

Refusals — first match wins; respond with the quoted line exactly and stop:

- **No PR or upstream diff.** `No PR or upstream diff. /eval-bugteam needs a target.`
- **Dirty tree.** `Uncommitted changes detected. Stash, commit, or revert before
  /eval-bugteam.`
- **Missing subagents.** Before Step 0, confirm `eval-code-quality-agent` and
  `eval-clean-coder` exist. Else: `Required subagent type <name> not installed.
  /eval-bugteam needs both eval-code-quality-agent and eval-clean-coder available.`

## Utility scripts

Shell-heavy steps live under
[`_shared/pr-loop/scripts/`](../../_shared/pr-loop/scripts/) (run, do not paste
into context). Utility scripts are **executed**, not loaded as primary context
([`sources.md`](sources.md) § Progressive disclosure and utility scripts).

### Pre-flight (before Step 0)

```bash
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/preflight.py"
```

Non-zero → fix before grant. `BUGTEAM_PREFLIGHT_SKIP=1` emergency only.
`--pre-commit` if `.pre-commit-config.yaml` exists.

**Auto-remediation for `core.hooksPath`:** when preflight fails with stderr
containing `core.hooksPath` (the message starts with `bugteam_preflight:
core.hooksPath is`, or `Git-side CODE_RULES enforcement is not active`), Claude
must auto-invoke the fix script — do not fall through to `AskUserQuestion`, do
not punt to the user, do not ask for confirmation:

```bash
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/fix_hookspath.py"
```

The fix script removes any non-canonical local-scope override on the active
repository, sets the global `core.hooksPath` to `~/.claude/hooks/git-hooks` if
missing or wrong, and re-runs `preflight.py`. Its exit code becomes the
preflight outcome. Exit 0 → continue to Step 0. Non-zero only when the
canonical hooks directory is missing (run `npx claude-dev-env .` first) or
`git config --global` writes are blocked. Other preflight failures (pytest,
pre-commit) still require manual fixes —
the auto-remediation only applies to the `core.hooksPath` failure mode.

## The Process

### Progress checklist

```
[ ] Step 0: project permissions granted
[ ] Step 1: PR scope resolved
[ ] Step 2: loop state set
[ ] Step 3: cycle complete (converged | cap reached | stuck | error)
[ ] Step 4: working tree clean
[ ] Step 4.5: PR description rewritten (or skip warning logged)
[ ] Step 5: project permissions revoked
[ ] Step 6: final report printed
```

### Step 0: Grant project permissions (once, first)

```bash
python \
"${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/"\
"grant_project_claude_permissions.py"
```

`${CLAUDE_SKILL_DIR}` is host-substituted before the shell runs (unlike normal
env expansion). Idempotent writes to `~/.claude/settings.json` from repo root.
Non-zero → stop. Revoke in Step 5 on every exit path.

### Step 1: Resolve PR scope (once)

Accept one or more PR numbers from the invocation. For each PR, call
`pull_request_read(method="get", pullNumber=N, owner=O, repo=R)` (falling back
to the merge-base diff path when no PR exists). Capture `all_prs = [{number, owner, repo, baseRef,
headRef, url}, ...]`. A single-PR invocation produces a one-element list and
follows the same downstream rules.

Keep: owner/repo, branches, PR number, URL — for all loops.

**`<run_temp_dir>`:** `Path(tempfile.gettempdir()) / run_name` where
`run_name = "bugteam-pr-<number>-<YYYYMMDDHHMMSS>"` for a single-PR invocation
or `"bugteam-<YYYYMMDDHHMMSS>"` for multi-PR. Lead resolves once to an absolute
path; every shell gets that literal string.

#### Per-PR workspace

For each PR in all_prs:

1. Create `<run_temp_dir>/pr-<N>/`.
2. Run `git worktree add "<run_temp_dir>/pr-<N>/worktree" origin/<headRef>`.
3. Record the absolute worktree path alongside the PR's other fields.

Background subagents for a PR operate inside that PR's worktree. Step 4
teardown runs `git worktree remove "<run_temp_dir>/pr-<N>/worktree"` for each
PR before the shared `rmtree`.

### Step 2: Loop state

**Loop state (lead; not a single script; per-PR):** The variables
below are tracked independently for each PR in `all_prs`. Each PR has its
own cycle, state, and exit reason.

```bash
round_number=<R>
loop_count=0
last_action="fresh"
last_findings='{"total": 0}'
audit_log=""
run_temp_dir="<absolute-path>/<run_name>"
starting_sha="$(git -C "<run_temp_dir>/pr-<N>/worktree" rev-parse HEAD)"
loop_comment_index=""
```

`round_number` is set from the invocation context (`per-tick.md` ROUND 1 or ROUND 2).

**Optional Groq-backed FIX (explicit opt-in only):** when the user explicitly
sets `BUGTEAM_FIX_IMPLEMENTER=groq-coder` before invocation, spawn the FIX
subagent with `subagent_type="groq-coder"`. Requires `GROQ_API_KEY` in the
environment (load from `packages/claude-dev-env/.env` when that file exists;
prompt the user to create it from `.env.example` if still unset). Any other
`BUGTEAM_FIX_IMPLEMENTER` value (or unset) uses `eval-clean-coder`.

**`--bugbot-retrigger` flag:** when present, the FIX subagent posts a `bugbot
run` issue comment via the Step 2.5 issue-comments fallback endpoint after
every successful FIX push, to re-trigger Cursor's bugbot on the new commit.

**`loop_comment_index`:** reset each AUDIT start; filled during AUDIT; FIX
consumes for replies; cleared after FIX. Entries: `{loop, finding_id,
finding_comment_id, finding_comment_url, used_fallback, fix_status}`.

### Step 2.5: PR comments (one review per loop)

**Who posts:** the AUDIT subagent posts one review per loop via MCP tool calls.
The FIX subagent posts replies after push. The lead's only PR write before
Step 4.5 is the final description rewrite.

Order: audit → buffer → validate anchors vs diff → three-step review POST
(create pending → add inline comments → submit pending).
Review body states counts; zero findings → still one review, `comments: []`,
body `## /eval-bugteam round <R> loop <L> audit: 0P0 / 0P1 / 0P2 → clean`.

**Payloads:** Use MCP tool calls. Body text with markdown (backticks,
newlines, quotes) passes through safely as string parameters — no temp files, no
jq, no shell pipes.

**Review POST** (three-step: create pending → add inline comments → submit
pending):

Step 1 — Create pending review:
```
pull_request_review_write(
  method="create",
  commitID=<head_sha_at_post_time>,
  owner=<owner>, repo=<repo>, pullNumber=<number>
)
```

Step 2 — Add one inline comment per anchored finding:
```
add_comment_to_pending_review(
  path=<path>, line=<line>, side="RIGHT",
  body=<finding_body>,
  owner=<owner>, repo=<repo>, pullNumber=<number>
)
```
For multi-line findings, also pass `start_line` and `start_side="RIGHT"`.

Step 3 — Submit pending review with body:
```
pull_request_review_write(
  method="submit_pending",
  event="COMMENT",
  body=<review_body_text>,
  owner=<owner>, repo=<repo>, pullNumber=<number>
)
```

**Fix reply:** `add_reply_to_pull_request_comment(commentId=<finding_comment_id>,
body=<reply_text>, owner=<owner>, repo=<repo>, pullNumber=<number>)`

**Review POST fails:** issue comment fallback:
`add_issue_comment(owner=<owner>, repo=<repo>, issue_number=<number>,
body=<fallback_text>)`

`<head_sha_at_post_time>`: `git rev-parse HEAD` in subagent cwd immediately
before POST.

**Review body template:**

```
## /eval-bugteam round <R> loop <L> audit: <P0>P0 / <P1>P1 / <P2>P2

### Findings without a diff anchor
(only if needed)
- **[severity] title** — <file>:<line> — <one-line description>
```

**Anchor fallback:** lines not in diff → omit from inline comments, list under
`### Findings without a diff anchor`; outcome `used_fallback="true"`, empty
`finding_comment_id`, `finding_comment_url` = parent review URL.

**POST failure fallback:** one issue comment with full text; all findings
`used_fallback="true"`, URLs = issue comment.

**Endpoints:** `pull_request_review_write`; `add_comment_to_pending_review`;
`add_reply_to_pull_request_comment`; fallback `add_issue_comment`.

### Step 3: The cycle

Run the AUDIT-FIX cycle for each PR in all_prs. The 10-loop cap applies per PR. Exit reasons (converged, cap reached,
stuck, error) are tracked per PR; the final report lists one outcome line per
PR.

**Gate:** `validate_content` / `hooks/blocking/code_rules_enforcer.py` on
PR-scoped files before every AUDIT
(`_shared/pr-loop/scripts/code_rules_gate.py`). Lead runs gate; eval-clean-coder
clears failures; then bugfind audits.

**Pre-cycle: walk prior eval-bugteam reviews end-first** (once per PR, after Step 2
and before iteration begins, when `last_action == "fresh"`). A re-invocation of
`/eval-bugteam` on a PR with prior loops detects whether the most recent loop already
cleaned this HEAD (short-circuit) and otherwise records that prior loops were
dirty so the AUDIT runs against the latest diff with that signal in mind:

```python
dirty_review_count = 0
all_reviews = pull_request_read(
    method="get_reviews", pullNumber=N, owner=O, repo=R
)
prior_reviews = [
    rev for rev in all_reviews
    if rev.get("body", "").startswith("## /eval-bugteam round ")
]
prior_reviews.sort(key=lambda rev: rev["submitted_at"], reverse=True)
```

Iterate from index 0 (most recent) toward older entries:

- An eval-bugteam review body that ends with `→ clean` is **clean**; any other `##
  /eval-bugteam round ...` body is **dirty**.
- For a dirty review, increment `dirty_review_count` by one. The review's
  specific finding bodies are not carried forward —
  bugteam's AUDIT regenerates
  findings against the current HEAD's diff each loop, so prior bodies are stale
  by definition. The count alone is the carried signal.
- Stop at the first clean review. Older reviews are presumed addressed at that
  clean checkpoint and are not re-read.
- When index 0 is itself clean AND its `commit_id` matches `git rev-parse HEAD`,
  the PR is already converged on this HEAD — set `last_action="audited"`,
  `last_findings='{"total": 0}'`, fall through to step 1's `converged` exit,
  skip Step 3 iteration entirely.
- When `dirty_review_count > 0`, log the count and proceed into the normal
  iteration; the next AUDIT regenerates anchored findings against the current
  HEAD so `loop_comment_index` stays correct. Unlike `pr-converge` — where
  Cursor Bugbot's prior dirty-review *bodies* are read back by the Fix protocol
  because each dirty body lists specific findings the loop must still address
  —
  bugteam's per-loop bodies are anchored to the diff at *that loop's* HEAD, so
  re-applying them against a newer diff would be incorrect. The count is
  sufficient signal that "prior loops did not converge here."

1. From `last_action` / `last_findings`:
   - `last_action == "audited"` and `last_findings.total == 0` → exit
     `converged`
   - `last_action == "fixed"` and `git rev-parse HEAD` unchanged since
     pre-FIX → exit `stuck`
   - `last_action in {"fresh", "fixed"}` → **pre-audit** then **AUDIT**
   - `last_action == "audited"` and `last_findings.total > 0`:
     - When ALL findings are P2 (style/compliance only), skip FIX
       and exit `converged`
     - Otherwise → **FIX**

2. **Pre-audit** (only when the next step is AUDIT):

   ```bash
   python \
     "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/code_rules_gate.py" \
     --base origin/<baseRefName>
   ```

Lead only; merge-base / diff semantics:
[`../../_shared/pr-loop/code-rules-gate.md`][path-code-rules]; shared script
inventory: [`../../_shared/pr-loop/scripts/README.md`][path-scripts-readme].
Non-zero → spawn **eval-clean-coder** standards-fix (read stderr, edit, re-run
**this same** command, one commit, `git push`, shutdown) until exit **0** or
**5**
failed gate rounds → `error: code rules gate failed pre-audit`. After **0**:
`loop_count += 1`; if `loop_count > 10` → `cap reached`. Then **AUDIT**
(bugfind); print `Loop <L> audit: ...`.

3. **FIX** (`last_action == "audited"` and `last_findings.total > 0`):
   `loop_count += 1`; if `loop_count > 10` → `cap reached`; **FIX** (bugfix);
   print `Loop <L> fix: ...`; `last_action = "fixed"`, update `audit_log`; loop
   to step 1.

4. After **AUDIT**: update `last_action`, `last_findings`, `audit_log`; print
   audit line if not already printed.

5. Loop.

First pass: pre-audit → AUDIT. After a FIX, the next pass runs pre-audit again
before the next AUDIT.

### AUDIT action

```bash
mkdir -p "<run_temp_dir>/pr-<N>"
```

Then call `pull_request_read(method="get_diff", pullNumber=N, owner=O, repo=R)`
to capture the diff text, and write it to
`"<run_temp_dir>/pr-<N>/loop-<L>.patch"` using the `Write` tool.

Call `pull_request_read(method="get", pullNumber=N, owner=O, repo=R)`, extract
the `.body` field from the response, and write it to
`"<run_temp_dir>/pr-<N>/loop-<L>.body.md"` using the `Write` tool.

Run the pre-audit gate capture (read-only snapshot for the auditor, not a
re-enforcement — the live gate runs in Step 3.2):

```bash
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/code_rules_gate.py" --base origin/<baseRefName> > "<run_temp_dir>/pr-<N>/loop-<L>.gate.txt" 2>&1 || true
```

The body file and gate-output file feed the AUDIT XML's `<scope>` and
`<gate_output>` sections.

**Spawn:**

```
Agent(
  subagent_type="eval-code-quality-agent",
  name="bugfind-pr<N>-loop<L>",
  model="opus",
  run_in_background=true,
  description="Bugfind audit PR <N> loop <L>",
  prompt="<audit XML; see PROMPTS.md>"
)
```

Lead awaits the background-completion notification (120s timeout). On
timeout: treat as a hard blocker and abort the loop.

Lead reads `<worktree_path>/.bugteam-pr<N>-loop<L>.outcomes.xml`, fills
`loop_comment_index`. [`PROMPTS.md`](PROMPTS.md): XML + outcome schema.

#### Lead-side audit triage (before FIX spawn)

Between reading the AUDIT outcome XML and spawning the FIX subagent, the lead inspects every `<finding>` for triage signals. The triage step exists because an audit recommendation that contradicts the live gate or breaks an unrelated fix produces an atomic-commit-blocked FIX, eats a loop, and reroutes to fix-protocol — the per-finding commit pattern in PROMPTS.md mitigates the blast radius, and this triage step prevents the false-positive from being attempted at all.

For each finding:

1. **Gate-consistency check.** When `gate_output_consistent="false"` and the finding's category implies hook-enforced behavior (Comments, Naming, Magic values, Constants location, Imports at top, Logging format, mypy, Type hints), demote the finding to `triage_demoted` and skip it from the FIX bug list. Reply on the inline thread: "Demoted by lead-side triage: predicted enforcer behavior the captured gate output does not exhibit. Reopen with concrete enforcer evidence."
2. **Adversarial-pass check.** When `adversarial_pass` names a real regression (drain loop, infinite retry, breaks caller, exposes secret, removes existing comment, breaks PR contract), confirm the finding's `recommended_fix_constraint` fences off that regression. When the constraint is empty or insufficient, demote the finding and reply: "Demoted by lead-side triage: adversarial pass names regression `<adversarial_pass>` without a fix constraint. Reopen with a constraint that fences the regression."
3. **No-deletion sanity check.** When the finding suggests editing or removing an existing comment, run `git diff origin/<baseRefName> -- <file>` and check whether the comment text on the current HEAD already differs from the base. When the current HEAD's comment is already the post-edit version, the no-deletion hook will block any revert; demote and reply: "Demoted by lead-side triage: comment is already in committed form on HEAD; revert would trip the no-deletion hook. Use AGENTS.md comment-edit exemption."
4. **Breaks-existing-tested-behavior check.** When the suggested fix would change a function signature, contract, or behavior that an existing committed test already locks in, demote the finding. To run this check: identify the function or symbol the finding targets, run `git grep -n "<symbol>" -- '*test*.py'` plus `Read` on every match, and verify the proposed change does not contradict an `assert`, expected return, or parametrized case in those tests. When a contradiction exists, demote with reason `breaks-existing-tested-behavior` and reply: "Demoted by lead-side triage: applying the suggested change would break committed test `<test_name>` at `<file>:<line>` (asserts `<excerpt>`). Reopen with a concrete production scenario that requires the change AND a separate refactor to update or remove the test, OR with a tighter recommendation that does not contradict the existing assertion."

Findings that pass triage advance to the FIX spawn unchanged. Demoted findings are recorded in `loop_comment_index` with `triage_status="demoted"` and `triage_reason="<one-line>"` — they do NOT count as `total` toward FIX gating, but they DO count as audit findings on the audit log line so cap-reached calculations remain accurate.

`last_action = "audited"`; append audit line to `audit_log`.

The sibling-output paths in [`PROMPTS.md`](PROMPTS.md) must cover the full
`-b` through `-k` range.

### FIX action

**Spawn:**

```
Agent(
  subagent_type="eval-clean-coder",
  name="bugfix-pr<N>-loop<L>",
  model="opus",
  run_in_background=true,
  description="Bugfix PR <N> loop <L>",
  prompt="<fix XML; see PROMPTS.md>"
)
```

Pass finding comment URLs/ids from `loop_comment_index` in XML. The FIX XML
in [`PROMPTS.md`](PROMPTS.md) uses per-finding commits: each finding is
processed independently with its own commit, post-fix grep verification, and
reply. Lead awaits the background-completion notification. Replies: `Fixed in
<sha>` or `Could not address this loop: <reason>`.

Verify from worktree: `git -C "<run_temp_dir>/pr-<N>/worktree" rev-parse HEAD`
advanced; `git -C "<run_temp_dir>/pr-<N>/worktree" fetch origin <branch> && git -C "<run_temp_dir>/pr-<N>/worktree" rev-parse origin/<branch>` matches
`HEAD`. Unchanged HEAD →
`stuck — bugfix subagent could not address findings`.

#### Lead-side post-FIX verification

For every outcome with `status="fixed"`, the lead independently verifies the change landed before accepting the loop as progress. The check exists because a FIX subagent's prose report is not ground truth — agent-claim-vs-reality drift produced one fix-regression per loop in prior runs.

For each `status="fixed"` outcome:

1. Read the per-finding `commit_sha`. Run `git -C "<run_temp_dir>/pr-<N>/worktree" show --stat <commit_sha>` to confirm the commit exists and touched the expected files.
2. Read the `post_fix_grep_pattern` and `post_fix_grep_hits` attributes the FIX subagent recorded.
3. Run `git -C "<run_temp_dir>/pr-<N>/worktree" grep -c -E "<post_fix_grep_pattern>" <file>` and compare the result to the recorded hit count. When they disagree, the FIX subagent's claim is unverified — log the divergence under `audit_log`, set the outcome's effective status to `unverified_fixed`, and treat it as `could_not_address` for next-loop AUDIT scope (the next AUDIT will see the finding's diff anchor unchanged and re-issue it).

When every `status="fixed"` outcome verifies, the loop counts as progress. When any outcome is downgraded to `unverified_fixed`, the loop count still increments but `last_action="fixed"` and `last_findings.total` reflect the unverified count so the next AUDIT pre-empts a stuck-detection false negative.

**Scope verification.** Run `git diff origin/<base>..HEAD --name-only` and compare against the set of files referenced in bugs_to_fix. When the commit touches any file NOT in the bugs_to_fix list, downgrade the outcome to `unverified_fixed` with reason "commit touched unexpected files: <list>".

### Step 4: Teardown

1. For each PR in `all_prs`: `git worktree remove
   "<run_temp_dir>/pr-<N>/worktree"` (from Step 1) — tolerate already-removed
   worktrees.

2. **Windows-safe `rmtree`** — strips the Windows ReadOnly attribute and retries
   the failing syscall (see `~/.claude/rules/windows-filesystem-safe.md`).
   Remove the full `<run_temp_dir>`.

### Step 4.5: PR description

Lead only; cumulative product narrative (not process). Delegate body to
`eval-pr-description-writer` via `Agent` (else `general-purpose`) so the
mandatory-pr-description hook accepts `update_pull_request`.

1. `pull_request_read(method="get_diff", pullNumber=N, owner=O, repo=R)` → write
   output to `.bugteam-final.diff` with `Write` tool.
2. `pull_request_read(method="get", pullNumber=N, owner=O, repo=R)` → extract
   `.body` from response, write to `.bugteam-original-body.md` with `Write` tool.
3. Agent brief: paths + branch names; describe merge-ready change from diff;
   keep curated original sections intact; return markdown body.
4. Write `.bugteam-final-body.md`; `update_pull_request(pullNumber=N, owner=O,
   repo=R, body=<body_text>)`.
5. Delete the three temp files.

On failure: log in final report; continue to Step 5.

### Step 5: Revoke permissions (always)

```bash
python \
"${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/"\
"revoke_project_claude_permissions.py"
```

Removes Step 0 grant — run even if Step 4 partially failed (log separately).

### Step 6: Final report

```
/eval-bugteam exit: <converged | cap reached | stuck | error>
Loops: <loop_count>
Starting commit: <starting_sha7>
Final commit: <current_HEAD_sha7>
Net change: <total_files> files, +<total_add>/-<total_del>

Loop log:
1 audit: 3P0 2P1 0P2
...
```

`cap reached` → suggest `/findbugs`. `stuck` → which findings. `error` →
detail + loop.

## Constraints

See [`CONSTRAINTS.md`](CONSTRAINTS.md).

## Examples

See [`EXAMPLES.md`](EXAMPLES.md).

## Reference

See [`reference/README.md`](reference/README.md).

## Sources

See [`sources.md`](sources.md).

[path-code-rules]: ../../_shared/pr-loop/code-rules-gate.md
[path-scripts-readme]: ../../_shared/pr-loop/scripts/README.md
