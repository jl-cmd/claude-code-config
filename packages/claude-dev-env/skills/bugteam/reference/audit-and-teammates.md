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

## AUDIT action (twelve fresh teammates per loop, two-phase)

Capture a fresh PR diff for this loop into the per-PR scoped directory so concurrent `/bugteam` runs keep patches isolated. Use the literal `<run_temp_dir>` resolved once in Step 2 — Claude resolves the absolute path; every shell receives the same literal value.

1. Create the directory: `mkdir -p "<run_temp_dir>/pr-<N>"`.
2. Call `pull_request_read(method="get_diff", pullNumber=N, owner=O, repo=R)` to capture the diff text, then write it to `"<run_temp_dir>/pr-<N>/loop-<L>.patch"` using the `Write` tool.

Every audit loop runs the two-phase, twelve-teammate flow defined in `SKILL.md` § AUDIT action: phase 1 spawns the eleven category auditors (`-a` through `-k`) in one assistant message; once **all eleven return**, phase 2 spawns the consolidator/validator (`-validate`). There is no single-auditor mode and no loop-count gate.

`<run_temp_dir>` includes the sanitized `team_name` and timestamp; `team_name` is already prefixed with `bugteam-`. Claude resolves `Path(tempfile.gettempdir()) / team_name` once and passes that absolute path to every shell. `tempfile.gettempdir()` honors `TMPDIR`, `TEMP`, `TMP` and falls back to the OS temp directory, so the same approach works on macOS, Linux, Windows cmd.exe, and PowerShell.

Each loop calls `Agent` twelve times with fresh invocations so every teammate starts with its own context window. Doc line on lead history: [`../sources.md`](../sources.md).

See [`../PROMPTS.md`](../PROMPTS.md) for AUDIT spawn-prompt XML, the per-letter category-auditor binding, the consolidator/validator schema, and the outcome schema. Substitute placeholders (`repo`, `branch`, `base_branch`, `pr_url`, `loop`, `diff_path`, `letter`) into the `prompt` argument.

After phase 2 completes, the lead reads `.bugteam-pr<N>-loop<L>.outcomes.xml` from the worktree directory with the `Read` tool, parses it, and populates `loop_comment_index` from `<finding>` elements.

### Shutdown (bugfind)

Each of the twelve teammates self-terminates when complete — the background-completion notification arrives and the lead advances to the next phase. If any phase 1 auditor fails to notify within the lead timeout (120s), treat as a hard blocker and abort the loop without spawning the consolidator/validator. If the consolidator/validator fails to notify within 120s, treat as a hard blocker and abort the loop.

`last_action = "audited"`. Append audit metadata to `audit_log`.

### AUDIT phase 1 — eleven category auditors in parallel (every loop)

The pre-audit gate must pass immediately before this step. There is no
loop-count gate: every audit loop runs the eleven category auditors in
parallel, then the single consolidator/validator after they all return.
Issue eleven `Agent` calls in **one** assistant message so phase 1 runs
fully in parallel:

```
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-a", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category A", prompt="<audit XML; bound to category A; load $HOME/.claude/audit-rubrics/category_rubrics/category-a-api-contracts.md and $HOME/.claude/audit-rubrics/prompts/category-a-api-contracts.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-a.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-b", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category B", prompt="<audit XML; bound to category B; load $HOME/.claude/audit-rubrics/category_rubrics/category-b-selector-engine-compat.md and $HOME/.claude/audit-rubrics/prompts/category-b-selector-engine-compat.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-b.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-c", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category C", prompt="<audit XML; bound to category C; load $HOME/.claude/audit-rubrics/category_rubrics/category-c-resource-cleanup.md and $HOME/.claude/audit-rubrics/prompts/category-c-resource-cleanup.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-c.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-d", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category D", prompt="<audit XML; bound to category D; load $HOME/.claude/audit-rubrics/category_rubrics/category-d-scoping-and-ordering.md and $HOME/.claude/audit-rubrics/prompts/category-d-scoping-and-ordering.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-d.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-e", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category E", prompt="<audit XML; bound to category E; load $HOME/.claude/audit-rubrics/category_rubrics/category-e-dead-code.md and $HOME/.claude/audit-rubrics/prompts/category-e-dead-code.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-e.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-f", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category F", prompt="<audit XML; bound to category F; load $HOME/.claude/audit-rubrics/category_rubrics/category-f-silent-failures.md and $HOME/.claude/audit-rubrics/prompts/category-f-silent-failures.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-f.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-g", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category G", prompt="<audit XML; bound to category G; load $HOME/.claude/audit-rubrics/category_rubrics/category-g-bounds-and-overflow.md and $HOME/.claude/audit-rubrics/prompts/category-g-bounds-and-overflow.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-g.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-h", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category H", prompt="<audit XML; bound to category H; load $HOME/.claude/audit-rubrics/category_rubrics/category-h-security-boundaries.md and $HOME/.claude/audit-rubrics/prompts/category-h-security-boundaries.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-h.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-i", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category I", prompt="<audit XML; bound to category I; load $HOME/.claude/audit-rubrics/category_rubrics/category-i-concurrency.md and $HOME/.claude/audit-rubrics/prompts/category-i-concurrency.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-i.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-j", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category J", prompt="<audit XML; bound to category J; load $HOME/.claude/audit-rubrics/category_rubrics/category-j-code-rules-compliance.md and $HOME/.claude/audit-rubrics/prompts/category-j-code-rules-compliance.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-j.outcomes.xml; skip PR posting>")
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-k", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind audit PR <N> loop <L> category K", prompt="<audit XML; bound to category K; load $HOME/.claude/audit-rubrics/category_rubrics/category-k-codebase-conflicts.md and $HOME/.claude/audit-rubrics/prompts/category-k-codebase-conflicts.md; write outcome to <run_temp_dir>/pr-<N>/loop-<L>-k.outcomes.xml; skip PR posting>")
```

Each category auditor is bound to one rubric file and one prompt file under `$HOME/.claude/audit-rubrics/`, and may file findings only for its bound category letter. None of the eleven posts to the PR — they only write per-letter XML.

The lead awaits **all eleven** background-completion notifications before moving to phase 2. If any of the eleven times out (120s), treat as a hard blocker and abort the loop; do not spawn the consolidator/validator with a partial sibling set.

### AUDIT phase 2 — consolidator/validator after the eleven return

Once every sibling XML at `<run_temp_dir>/pr-<N>/loop-<L>-{a..k}.outcomes.xml` is on disk, spawn the consolidator/validator in a fresh `Agent` call (`run_in_background=true`):

```
Agent(subagent_type="code-quality-agent", name="bugfind-pr<N>-loop<L>-validate", team_name="<team_name>", model="opus", run_in_background=true, description="Bugfind consolidate/validate PR <N> loop <L>", prompt="<validate XML; read each of the 11 sibling XMLs at <run_temp_dir>/pr-<N>/loop-<L>-a.outcomes.xml through <run_temp_dir>/pr-<N>/loop-<L>-k.outcomes.xml (literal absolute paths, all already on disk); validate each finding: file exists, line in bounds, excerpt matches claimed line, category matches the auditor's bound letter, category A-K, severity P0/P1/P2; quarantine hallucinated findings to <run_temp_dir>/pr-<N>/loop-<L>-diagnostics.json under validator_rejected; de-dup by (file, line, category), max severity wins, keep longest description on conflict; re-id as loop<L>-<K>; write <worktree_path>/.bugteam-pr<N>-loop<L>.outcomes.xml; before posting, re-read the full review once as the PR author would — merge duplicates, drop findings that miss their mark, rephrase anything confusing — your job is to make the author want to fix these bugs, not to demonstrate the rubric ran; then post review>")
```

Teammate `-validate` is the opus consolidator/validator: reads all eleven sibling XMLs at explicit absolute paths under `<run_temp_dir>/pr-<N>` (no polling — the lead has already confirmed the files are on disk), then validates each finding: file exists, line in bounds, excerpt matches claimed line, category matches the auditor's bound letter, category is A–K, severity is P0/P1/P2. Hallucinated findings are quarantined to `<run_temp_dir>/pr-<N>/loop-<L>-diagnostics.json` under `validator_rejected`. Valid findings are de-duplicated by `(file, line, category)` (max severity wins, keep longest description on conflict) and re-assigned merged IDs as `loop<L>-<K>`. The `-validate` prompt must embed sibling paths as literal absolutes so `Read` works without discovery.

All subagents self-terminate via background completion. The lead awaits the eleven category auditors in phase 1 and then the consolidator/validator notification in phase 2 (120s timeout each). Missing notification → hard blocker.

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

Substitute placeholders from `last_findings` into the fix prompt per [`../PROMPTS.md`](../PROMPTS.md).

**Verify push:** `git rev-parse HEAD` after fix must differ from before; new HEAD must exist on `origin/<branch>` (`git fetch origin <branch> && git rev-parse origin/<branch>` matches `HEAD`). If HEAD did not change → `stuck — bugfix teammate could not address findings`.

**Scope verification.** Run `git diff HEAD~1 --name-only` and compare against the set of files referenced in `bugs_to_fix`. When the commit touches files NOT in the `bugs_to_fix` list, judge whether the extras are a coherent part of the fix: a shared helper the auditor did not think to name, a test file that exercises the fix, a config update the fix requires. If the extras are coherent with the fix, note them in the outcome XML's `<scope_notes>` and keep the outcome as `fixed`. If the extras look unrelated, suspicious, or out of scope, downgrade to `unverified_fixed` with reason `commit touched unexpected files: <list>`. The auditor's file list is a default, not a contract — the fix's coherence is the contract.

`last_action = "fixed"`. Append fix line to `audit_log`.
