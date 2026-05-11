# Gate, cycle, AUDIT, and FIX

## Pre-cycle: walk prior bugteam reviews end-first

**Pre-cycle: walk prior bugteam reviews end-first** (once per PR, after Step 2
and before iteration begins, when `last_action == "fresh"`). A re-invocation of
`/bugteam` on a PR with prior loops detects whether the most recent loop already
cleaned this HEAD (short-circuit) and otherwise records that prior loops were
dirty so the AUDIT runs against the latest diff with that signal in mind:

```python
dirty_review_count = 0
all_reviews = pull_request_read(
    method="get_reviews", pullNumber=N, owner=O, repo=R
)
prior_reviews = [
    rev for rev in all_reviews
    if rev.get("body", "").startswith("## /bugteam loop ")
]
prior_reviews.sort(key=lambda rev: rev["submitted_at"], reverse=True)
```

Iterate from index 0 (most recent) toward older entries:

- A bugteam review body that ends with `→ clean` is **clean**; any other `##
  /bugteam loop ...` body is **dirty**.
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

## Step 3 — The cycle (full detail)

Repeat until an exit condition fires.

**Ordering principle:** Mandatory **CODE_RULES** checks (`validate_content` from `hooks/blocking/code_rules_enforcer.py`) must pass on the PR-scoped file set **before** any **AUDIT** (bugfind) teammate runs. The **clean-coder** teammate clears gate failures; then the **code-quality-agent** teammate audits. This mirrors “CI green, then review,” without relying on GitHub Actions — the script is the gate.

1. Decide the next action from `last_action` and `last_findings`:
   - `last_action == "audited"` and `last_findings.total == 0` → exit reason = `converged`
   - `last_action == "fixed"` and `git rev-parse HEAD` did not change since pre-FIX → exit reason = `stuck` (see FIX action)
   - `last_action in {"fresh", "fixed"}` → go to **pre-audit path** (below), then **AUDIT**
   - `last_action == "audited"` and `last_findings.total > 0` → go to **FIX** (below)

2. **Pre-audit path** (only when the next step is **AUDIT**):
   1. From the repository root, run the gate script (align `--base` with the PR base branch from Step 1, e.g. `origin/main` or `origin/develop`):

      ```bash
      python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/code_rules_gate.py" --base origin/<baseRefName>
      ```

      `git merge-base` + `git diff --name-only` live inside the script; see [`../../../_shared/pr-loop/scripts/README.md`](../../../_shared/pr-loop/scripts/README.md) for what lives under this directory, and [`../../../_shared/pr-loop/code-rules-gate.md`](../../../_shared/pr-loop/code-rules-gate.md) for gate-only merge-base / invocation semantics. The lead runs this (not a teammate).

   2. If exit code **0** → continue to step 2.5 (AUDIT spawn) below.
   3. If exit code **non-zero** → spawn a new **clean-coder** teammate (`mode="bypassPermissions"`) — **standards-fix pass** — with instructions: read the script’s stderr, edit the repo until a **re-run** of the **same** gate command exits **0**, then one commit, `git push`, shutdown. Repeat standards-fix spawns until the gate exits **0** or **5** failed gate rounds (each round = one teammate session after a non-zero gate). If still non-zero after 5 rounds → exit reason = `error: code rules gate failed pre-audit`.
   4. After gate exit **0**, increment `loop_count`. If `loop_count > 20`, exit reason = `cap reached` (counts **audits**, not standards-only rounds).
   5. Execute **AUDIT action** (spawn bugfind). Print progress: `Loop <L> audit: ...`

3. **FIX path** (when `last_action == "audited"` and `last_findings.total > 0`):
   1. Increment `loop_count`. If `loop_count > 20`, exit reason = `cap reached`.
   2. Execute **FIX action** (spawn bugfix clean-coder for audit findings). Print: `Loop <L> fix: commit ...`
   3. Set `last_action = "fixed"`, update `audit_log`, loop to step 1 (next iteration hits **pre-audit path** before the next AUDIT).

4. After **AUDIT**, update `last_action`, `last_findings`, `audit_log`; print the audit progress line if not already printed.

5. Loop.

**Note:** The first iteration uses **pre-audit path** then **AUDIT**. After a **FIX**, the next iteration runs **pre-audit path** again (gate → then AUDIT), so `validate_content` stays green before semantic audit.

## AUDIT action (eleven task-based teammates per loop, two-phase)

Capture a fresh PR diff for this loop into the per-PR scoped directory so concurrent `/bugteam` runs keep patches isolated. Use the literal `<run_temp_dir>` resolved once in Step 2 — Claude resolves the absolute path; every shell receives the same literal value.

1. Create the directory: `mkdir -p "<run_temp_dir>/pr-<N>"`.
2. Call `pull_request_read(method="get_diff", pullNumber=N, owner=O, repo=R)` to capture the diff text, then write it to `"<run_temp_dir>/pr-<N>/loop-<L>.patch"` using the `Write` tool.

Every audit loop runs the two-phase flow defined in `SKILL.md` § AUDIT action: the lead spawns eleven category-auditor teammates into the master `bugteam` team (tasks created once in Step 2, reset between loops). Once **all eleven audit tasks are complete**, the lead spawns the consolidator/validator teammate, then handles cleanup.

`<run_temp_dir>` is the deterministic path resolved in Step 2. Tasks and the team config persist in `~/.claude/tasks/bugteam/` and `~/.claude/teams/bugteam/` across sessions — the lead re-enters by listing tasks and re-spawning any incomplete auditors.

Each loop creates 11 tasks and spawns 11 teammates with fresh invocations. Doc line on lead history: [`../sources.md`](../sources.md).

See [`../PROMPTS.md`](../PROMPTS.md) for AUDIT spawn-prompt XML, the per-letter category-auditor binding, the consolidator/validator schema, and the outcome schema. The spawn XML includes TaskCreate/self_audit_checklist for task tracking — every consolidator/validator MUST create tasks before starting. Substitute placeholders (`repo`, `branch`, `base_branch`, `pr_url`, `loop`, `diff_path`, `letter`) into the `prompt` argument.

After phase 2 completes, the lead reads `.bugteam-pr<N>-loop<L>.outcomes.xml` from the worktree directory with the `Read` tool, parses it, and populates `loop_comment_index` from `<finding>` elements.

### Shutdown (bugfind)

Each teammate self-terminates after marking its task complete — the task list reflects completion. The lead polls `TaskList` to detect when all eleven tasks are `completed`. Tasks that stay `in_progress` without an idle notification signal a crashed teammate. For each stuck task: verify whether the outcome XML exists at `<run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}-{letter}.outcomes.xml`. XML present → mark task `completed` (teammate finished, crashed before marking). No XML → re-spawn that letter's teammate.

`last_action = "audited"`. Append audit metadata to `audit_log`.

### AUDIT phase 1 — eleven category auditors as teammates (every loop)

The pre-audit gate must pass immediately before this step. Every audit loop
creates 11 tasks and spawns 11 teammates into the master `bugteam` team
(created once in Step 2). Each teammate self-claims a task by subject prefix,
audits its category, writes outcome XML, marks the task complete, and shuts down.

**Task creation (once per invocation):** After team creation in Step 2, issue 13
`TaskCreate` calls in **one** assistant message. These tasks persist across
all audit loops — the cleanup task resets them to `pending` between loops.

```
TaskCreate(subject="{owner}/{repo}#{N} audit {letter} loop {L}",
           description="Audit category {letter} for {owner}/{repo}#{N}. "
                       "Loop number in subject is updated by cleanup at end of each loop. "
                       "Load rubric from $HOME/.claude/audit-rubrics/category_rubrics/category-{letter}-{slug}.md. "
                       "Load prompt from $HOME/.claude/audit-rubrics/prompts/category-{letter}-{slug}.md. "
                       "Diff: <run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}.patch. "
                       "Write outcome XML to <run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}-{letter}.outcomes.xml. "
                       "Worktree: <worktree_path>.")
# ... (11 calls, A through K)
TaskCreate(subject="{owner}/{repo}#{N} consolidate loop {L}",
           description="Consolidate and validate all 11 audit outcome XMLs for {owner}/{repo}#{N}. "
                       "Loop number in subject is updated by cleanup at end of each loop. "
                       "Read sibling XMLs from <run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}-{a..k}.outcomes.xml. "
                       "Validate, de-dup, post review. Write <worktree_path>/.bugteam-pr<N>-loop<L>.outcomes.xml.")
TaskCreate(subject="{owner}/{repo}#{N} cleanup loop {L}",
           description="Reset task list for next audit loop on {owner}/{repo}#{N}. "
                       "Lead-managed: after consolidator completes, update this task to completed, "
                       "then reset all 12 other tasks to pending and update their loop number in subject.")
```

Between loops, the lead claims and completes the cleanup task, then resets
all 12 other tasks to `pending` via `TaskUpdate` — ready for the next loop's
teammates to claim.

**Teammate spawn:** Issue 11 `Agent` calls in **one** assistant message:

```
Agent(subagent_type="code-quality-agent",
      name="bugfind-{owner}-{repo}-pr{N}-loop{L}-{letter}",
      team_name="bugteam",
      model="opus",
      run_in_background=true,
      description="Audit {owner}/{repo}#{N} loop {L} category {letter}",
      prompt="<audit XML; claim task by subject prefix; bound to category {letter}; load rubric and prompt; write outcome XML; mark task complete; shutdown>")
```

**Recovery (re-entry or API error):** Before spawning, the lead lists tasks
(`TaskList`). For each task with status `pending` or `in_progress`:

- Check if the outcome XML exists at `<run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}-{letter}.outcomes.xml`
- If XML exists → teammate finished but crashed before marking; call `TaskUpdate` to `completed`
- If no XML → re-spawn that letter's teammate

Tasks already `completed` are skipped.

Each category auditor is bound to one rubric file and one prompt file under
`$HOME/.claude/audit-rubrics/`, and may file findings only for its bound
category letter. None of the eleven posts to the PR — they only write
per-letter XML.

The lead polls `TaskList` until all eleven tasks are `completed`, then
verifies every XML is on disk before spawning phase 2.

### AUDIT phase 2 — consolidator/validator after all eleven complete

Once every sibling XML at `<run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}-{a..k}.outcomes.xml`
is on disk, spawn the consolidator/validator in a fresh `Agent` call
(`run_in_background=true`):

```
Agent(subagent_type="code-quality-agent",
      name="bugfind-{owner}-{repo}-pr{N}-loop{L}-validate",
      team_name="bugteam",
      model="opus",
      run_in_background=true,
      description="Consolidate/validate {owner}/{repo}#{N} loop {L}",
      prompt="<validate XML; read each of the 11 sibling XMLs at <run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}-a.outcomes.xml through <run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}-k.outcomes.xml (literal absolute paths, all already on disk); validate each finding: file exists, line in bounds, excerpt matches claimed line, category matches the auditor's bound letter, category A-K, severity P0/P1/P2; quarantine hallucinated findings to <run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}-diagnostics.json under validator_rejected; de-dup by (file, line, category), max severity wins, keep longest description on conflict; re-id as loop<L>-<K>; write <worktree_path>/.bugteam-pr<N>-loop<L>.outcomes.xml; before posting, re-read the full review once as the PR author would — merge duplicates, drop findings that miss their mark, rephrase anything confusing — your job is to make the author want to fix these bugs, not to demonstrate the rubric ran; then post review>")
```

Teammate `-validate` is the opus consolidator/validator: reads all eleven
sibling XMLs at explicit absolute paths under `<run_temp_dir>/{owner}-{repo}-pr-{N}`
(no polling — the lead has already confirmed the files are on disk), then
validates each finding: file exists, line in bounds, excerpt matches claimed
line, category matches the auditor's bound letter, category is A–K, severity
is P0/P1/P2. Hallucinated findings are quarantined to
`<run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}-diagnostics.json` under
`validator_rejected`. Valid findings are de-duplicated by `(file, line, category)`
(max severity wins, keep longest description on conflict) and re-assigned
merged IDs as `loop<L>-<K>`. The `-validate` prompt must embed sibling paths
as literal absolutes so `Read` works without discovery.

After the consolidator posts its review and returns, the lead terminates any
remaining teammates and proceeds to FIX or convergence.

## FIX action (fresh teammate)

Spawn:

```
Agent(
  subagent_type="clean-coder",
  name="bugfix-pr<N>-loop<L>",
  model="opus",
  mode="bypassPermissions",
  run_in_background=true,
  description="Bugfix PR <N> loop <L>",
  prompt="<fix XML; see PROMPTS.md>"
)
```

The teammate sees only the latest audit’s findings — each `Agent` call starts with a fresh context window; prior-loop findings, fix history, and chat stay in the lead.

Pass finding comment URL and id for each finding (from `loop_comment_index`) in the XML prompt so the teammate owns replies. After commit: one reply per finding (`Fixed in <commit_sha>` or `Could not address this loop: <one-line reason>`). Same identity model as bugfind: teammate posts; lead waits.

After replies, the teammate writes outcome XML (schema in [`../PROMPTS.md`](../PROMPTS.md)).

### Shutdown (bugfix)

Same self-termination model as bugfind. Missing notification → hard blocker.

`approve: false` → `error: bugfix teammate refused shutdown` → Step 4 then 5.

Substitute placeholders from `last_findings` into the fix prompt per [`../PROMPTS.md`](../PROMPTS.md). The spawn XML includes TaskCreate/self_audit_checklist for task tracking — the FIX subagent MUST create tasks before starting.

**Verify push:** `git rev-parse HEAD` after fix must differ from before; new HEAD must exist on `origin/<branch>` (`git fetch origin <branch> && git rev-parse origin/<branch>` matches `HEAD`). If HEAD did not change → `stuck — bugfix teammate could not address findings`.

**Scope verification.** Run `git diff HEAD~1 --name-only` and compare against the set of files referenced in `bugs_to_fix`. When the commit touches files NOT in the `bugs_to_fix` list, judge whether the extras are a coherent part of the fix: a shared helper the auditor did not think to name, a test file that exercises the fix, a config update the fix requires. If the extras are coherent with the fix, note them in the outcome XML's `<scope_notes>` and keep the outcome as `fixed`. If the extras look unrelated, suspicious, or out of scope, downgrade to `unverified_fixed` with reason `commit touched unexpected files: <list>`. The auditor's file list is a default, not a contract — the fix's coherence is the contract.

`last_action = "fixed"`. Append fix line to `audit_log`.
