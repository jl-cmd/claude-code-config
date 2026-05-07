---
name: self-improve-pr-converge
description: >-
  Daily gap analysis loop that reviews yesterday's bugteam/pr-converge runs from
  session transcripts, identifies gaps in the skill files via 5 concrete tests,
  implements improvements in a temp copy, evaluates against the baseline, and
  opens a draft PR when the improvement measurably outperforms.
  Triggered by Claude Desktop scheduled tasks (not CronCreate).
---

# Self-Improve PR Converge

**Core principle:** Yesterday's runs are the baseline. Extract structured metrics from session transcripts, run 5 gap-detection tests against extraction results, cross-reference findings against current skill text to find missing constraints, formulate improvements and validate them against the baseline before promoting.

## Contents

- When this skill applies — trigger conditions and refusal cases
- Data sources — skill files (targets), session transcripts (data), supporting data
- The Process — step-by-step workflow
  - Step 0: Resolve date window
  - Step 1: Find candidate sessions
  - Step 2: Extract structured data per session
  - Step 3: Run gap-detection tests
  - Step 4: Cross-reference against existing skill text
  - Step 5: Formulate improvement
  - Step 6: Temp-skill evaluation
  - Step 7: Promote or discard
  - Step 8: PR and report
- Test reference — the 5 gap-detection tests
- Eval baseline protocol — proving improvement is real
- Constraints — boundaries and invariants
- Output format

## When this skill applies

The skill is designed to be triggered by a Claude Desktop scheduled task (daily). It is not invoked via `/slash` command.

Refusals — first match wins; respond with the quoted line exactly and stop:

- **No sessions found.** `No bugteam/pr-converge sessions found in the last 24 hours.`
- **No gaps confirmed.** `No actionable gaps found. Evidence threshold not met.`
- **Dirty tree in skill repo.** `Uncommitted changes in claude-code-config. Stash or commit before running self-improve.`

## Data sources

### Skill files (the targets for improvement)

Paths are repo-root-relative. All reside in `claude-code-config`:

- `packages/claude-dev-env/skills/bugteam/` — SKILL.md, PROMPTS.md, CONSTRAINTS.md, reference/*.md
- `packages/claude-dev-env/skills/pr-converge/` — SKILL.md, reference/*.md (especially fix-protocol.md, per-tick.md, ground-rules.md)
- `packages/claude-dev-env/skills/findbugs/SKILL.md`
- `packages/claude-dev-env/skills/fixbugs/SKILL.md`
- `packages/claude-dev-env/_shared/pr-loop/` — fix-protocol.md, state-schema.md, audit-contract.md, scripts/

### Session transcripts (data for gap detection)

JSONL session transcript files from prior Claude Code sessions. These are the primary data source for bugteam/pr-converge run results.

**Primary search via Everything MCP:**

1. Find session transcript JSONL files:
   ```
   mcp__everything__everything_search(
     params={
       query: "jsonl",
       sort: "date-modified-desc",
       max_results: 200
     }
   )
   ```
   Note: Use `query: "jsonl"` (simple extension match). Do NOT use `everything_find_recent` — its period-based filtering may return empty. Do NOT use path-prefixed queries — Everything's query syntax does not support `\\` path separators in the query string. Filter results client-side by path containment (`~/.claude/projects/`) and date.

2. Filter to session-level transcripts. Exclude paths containing `\subagents\` (per-tick subagent transcripts). Session-level files are `<uuid>.jsonl` directly under a project directory like `Y--Projects-temp-python-automation-eval\`. Include only files with `.claude\projects\` in the path to restrict to Claude Code session transcripts.

3. Run the bundled runner script against all candidate paths. It performs marker scanning, extraction, and gap-detection in one call:

   ```
   Bash(python <worktree-root>/.../scripts/run_self_improve.py <paths...>)
   ```

   Outputs a single JSON report to stdout with markers found, session metrics, and gap-test results. No temp files needed — capture from the tool result.

4. Collect results into `candidate_sessions[]` with path, mtime, and matched markers.

### Supporting data

- **Git history on both repos** (claude-code-config, python-automation-eval) — commit SHAs, file lists, diffs, PR numbers
- **Plan files at `~/.claude/plans/*.md`** — may contain aggregated run summaries from prior eval sessions

## The Process

### Step 0: Resolve date window

Set `window_start = now - 24h`. All session transcript filtering uses this boundary. Append a flag for the final report showing the window.

### Step 1: Find candidate sessions

Search order — try each source until at least one candidate is found:

**Source A — JSONL session transcripts (raw data, primary):**

1. **Find candidate files** via Everything MCP:
   ```
   mcp__everything__everything_search(
     params={query: "jsonl", sort: "date-modified-desc", max_results: 200}
   )
   ```
   Filter results to include only paths containing `.claude\projects\`.

2. **Filter to session-level transcripts.** Exclude paths containing `\subagents\`. Session-level files are `<uuid>.jsonl` directly under a project directory.

3. **Run the pipeline.** Use the bundled runner to scan markers, extract metrics, and run gap-detection tests in one call:

   ```
   Bash(python <worktree-root>/packages/claude-dev-env/skills/self-improve-pr-converge/scripts/run_self_improve.py <paths...>)
   ```

   The runner's `sys.path` is self-contained — it runs correctly from any working directory when given absolute file paths. Outputs a single JSON report to stdout with fields: `status`, `confirmed_gap_count`, `session_metrics[]`, `gap_tests[]`, `markers_found[]`. Read the tool result directly — no temp file needed.

4. Collect matched files into `candidate_sessions[]` with path, mtime, and matched markers.

**Source B — Plan files:**

1. Find plan files via Everything MCP:
   ```
   mcp__everything__everything_find_recent(
     params={period: "24h", path: r"~/.claude/plans", extensions: "md", max_results: 50}
   )
   ```
2. Grep for markers: `bugteam`, `pr-converge`, `eval-bugteam`, `loop_count`.
3. Plan files may contain aggregated run summaries when raw transcripts are unavailable.

If all sources return empty: refuse with "No bugteam/pr-converge sessions found in the last 24 hours."

### Step 2: Extract structured data per session

Already handled by the unified runner in Step 1 — the `run_self_improve.py` script performs marker scanning, extraction, and gap-detection in one call. Skip this step unless running with `--extract-only` for debug purposes.

### Step 3: Run gap-detection tests

Already performed by the unified runner. Read the JSON output from Step 1:

- If `status: "no-action"` with reason matching no-sessions or no-gaps → refuse per the When-this-applies rules.
- If `confirmed_gap_count > 0` → proceed to Step 4. The `gap_tests` array lists which tests confirmed, with evidence per occurrence.
- If `confirmed_gap_count == 0` but `single_occurrences` exist → log them to `self-improve-eval-data/<date>/single-occurrences.json`, then refuse with "No actionable gaps found. Evidence threshold not met."

### Step 4: Cross-reference against existing skill text

For each confirmed gap, identify which skill file and section would need a fix:

1. Which test detected the gap → maps to which constraint domain (see [Test reference](#test-reference): each test maps to a specific constraint type and target skill area).
2. Read the relevant section of the target skill file. Determine if the constraint already exists:
   - If the constraint text already covers the gap → skip (already addressed).
   - If the constraint does not exist or is insufficiently narrow → actionable.
3. For actionable gaps, record: `{gap, target_file, target_section, existing_text (excerpt), proposed_constraint_text}`.

### Step 5: Formulate improvement

For each actionable gap, write:
- (a) The test that failed and the evidence from Step 2-3
- (b) The exact text to add and where in the target file
- (c) A brief rationale tying the failure to the proposed constraint

### Step 6: Temp-skill evaluation

Before modifying production skill files, the improvement must be validated against the baseline using GitHub MCP tools exclusively — no git or gh CLI operations.

1. **Identify eval PR.** From the extracted data, pick a PR with a full bugteam run in the date window, known loop count, known finding regressions, and known final outcome. Record its number, base SHA, and loop metrics as the **baseline**.

2. **Read baseline skill files.** Use `mcp__plugin_github_github__get_file_contents(owner, repo, path, ref="refs/heads/main")` to read the target skill file at the baseline state. The baseline SHA maps to the main branch tip when the data was captured.

3. **Create temp copy.** Write the baseline content to a local temp file: `<file>.temp-<feature>`. Keep the production skill untouched.

4. **Apply improvement.** Edit the temp copy with the proposed constraint text.

5. **Evaluate constraint effectiveness against the PR.** Read the PR's diff and apply the proposed constraints as the evaluation rubric. Use GitHub MCP tools:
   - `mcp__plugin_github_github__pull_request_read(method="get_diff", owner, repo, pullNumber)` to get the PR diff that was active during the baseline run
   - `mcp__plugin_github_github__pull_request_read(method="get_files", owner, repo, pullNumber)` to list changed files
   - `mcp__plugin_github_github__get_commit(sha=<baseline_base_sha>, owner, repo)` to confirm the commit state
   
   For each gap-detection test that failed in the baseline, determine whether the proposed constraint text would have prevented the failure. A metric scores as "Prevented" only when all three enforceability gates pass:
   - **Actionable.** The constraint tells the agent to DO a concrete thing (a specific check, a specific exclusion, a specific verification step). General exhortations ("be careful", "don't introduce bugs", "maintain quality") are not actionable.
   - **Verifiable.** A reviewer or automated tool could check whether the constraint was followed (e.g., "modify only files listed in bugs_to_fix" is verifiable via diff; "preserve existing comments" is verifiable via diff; "don't regress" is not verifiable before commit).
   - **Negative scope.** The constraint names what is out of bounds — files not to touch, helpers not to inline, patterns to preserve. Outcome-only constraints ("the fix must be clean") without a negative scope are not enforceable on their own.

   If any gate fails, the metric scores as "Not addressed" regardless of apparent relevance to the failure mode.

6. **Capture comparison metrics.** Score the proposed improvement against each metric:

   | Metric | Baseline | Projected with improvement | Verdict |
   |--------|----------|---------------------------|---------|
   | Loop count | (from extraction) | Prevented / Not addressed | Improvement? |
   | Finding regressions | (from extraction) | Prevented / Not addressed | Improvement? |
   | Scope violations | (from extraction) | Prevented / Not addressed | Improvement? |
   | Verified-clean depth | (from extraction) | Prevented / Not addressed | Improvement? |

### Step 7: Promote or discard

- **Promote:** The proposed improvement addresses at least 2 of the 4 metrics (scored as "Prevented" in Step 6) and passes all three enforceability gates (actionable, verifiable, negative scope). Apply the improvement to the production skill file. Commit as a single commit.
- **Discard:** The improvement addresses 0-1 metrics, or fails any enforceability gate. Remove the temp copy. Log the result to `self-improve-eval-data/<date>/discarded-improvements.json` with the constraint text, which gates failed, and the metrics it would not have prevented.
- **Mixed signal:** Not applicable with constraint-effectiveness evaluation. If the improvement addresses 2+ metrics, promote. If fewer, discard.

### Step 8: PR and report

Create a draft PR containing only the promoted improvements. Each improvement in the PR body includes:

- The test that failed and the evidence (which session, which loop, counts)
- The constraint text added and where
- The baseline vs test-run comparison table

PR title format: `feat(self-improve): <short description of constraint changes>`

Final report format:

```
/self-improve-pr-converge exit: <promoted | discarded | no-action>
Date window: <start> to <end>
Sessions scanned: <N>
Candidate sessions: <N> (with bugteam/pr-converge markers)
Tests run: <N> per session (5 tests × <candidate_count> sessions)
Confirmed gaps: <N> (2+ occurrence threshold)
  - <test_name>: <file> §<section> → <action: promoted|discarded|already-covered>
Single occurrences (not acted on): <N> → <path>
Production files modified: [<files>]
PR: <url>
```

## Test reference

### Evidence threshold

A gap is confirmed only when the same test fails in 2+ distinct runs (within or across sessions). Single failures are logged as "observed once, not yet confirmed" and suppressed from the improvement output.

### Test 1: FIX regression test

Checks whether FIX agent loops introduce new bugs.

- **Input:** Loop log with per-loop finding counts (total findings per loop).
- **Procedure:** Walk the loop log in order. For each consecutive pair (loop N, loop N+1): compute `findings_total(N+1) > findings_total(N)`.
- **Fail condition:** Any loop N+1 has more total findings than loop N.
- **Fail message template:** `Loop <N+1> has more findings (<count_N+1>) than loop <N> (<count_N>). This means FIX agent loop <N> introduced new bugs. Check whether the FIX constraints in PROMPTS.md adequately prevent scope-creep.`
- **Pass condition:** Finding counts are flat or strictly decreasing across all consecutive pairs.
- **Maps to:** `bugteam/PROMPTS.md` FIX spawn XML `<constraints>` section, and `_shared/pr-loop/fix-protocol.md` step 8 post-fix self-audit.

### Test 2: Scope violation test

Checks whether FIX agents modify files outside the bug list.

- **Input:** Per-loop FIX commit SHAs and the `bugs_to_fix` file list (extracted from the FIX agent prompt or outcome XML).
- **Procedure:** For each FIX commit, run `git diff HEAD~1 --name-only` (or equivalent against the commit parent) and compare against the file list that was in `bugs_to_fix`. Collect any files that appear in the diff but not in the bug list.
- **Fail condition:** Any FIX commit touches at least one file not listed in `bugs_to_fix`.
- **Fail message template:** `Commit <sha> touched <unexpected_files_list> which were not in bugs_to_fix. The FIX agent exceeded the narrow-scope constraint.`
- **Pass condition:** Every touched file was in the bug list.
- **Maps to:** `bugteam/PROMPTS.md` FIX spawn XML `<constraints><execution>` — the constraint on modifying only referenced files.

### Test 3: Cross-file drift test

Checks for hardcoded config values in test files that diverge from production config.

- **Input:** The full list of changed files from each FIX commit diff (including test files).
- **Procedure:** For each test file in the diff, search for hardcoded values (string literals, numeric literals > 5 lines from config imports) that match config constant patterns. Cross-reference against the production config in `config/`. Collect any mismatches where a test hardcodes a value that should reference a config constant.
- **Fail condition:** Any test file hardcodes a value that has a corresponding config constant with a different value.
- **Fail message template:** `Test file <path> hardcodes a value (<value>) that diverges from the config constant in <config_path>. The audit rubric didn't catch this config-test drift.`
- **Pass condition:** No config-vs-test mismatches found.
- **Maps to:** `bugteam/PROMPTS.md` AUDIT category J (magic values and configuration drift), and `code-quality-agent`'s audit rubric.

### Test 4: Verified-clean depth test

Checks the quality of verified-clean entries in audit results.

- **Input:** The audit outcome XML, specifically `<verified_clean>` entries for each bug category.
- **Procedure:** For each `<verified_clean>` entry, read the `evidence` attribute. Determine if it names a specific execution path from entry to exit (function name, control flow path, specific check) or is vague.
- **Criteria for "shallow":** Contains phrases like "no issues found", "pattern appears correct", "looks good", "seems fine", or any statement that does not name a specific function, variable, code path, or check performed.
- **Fail condition:** Any verified-clean entry is shallow by the criteria above.
- **Fail message template:** `Category <letter> was marked clean with shallow evidence: '<quote>'. The depth requirement was not met — evidence must name the function, the path traced, and the specific check performed.`
- **Pass condition:** Every clean entry names the function, the path traced, and the specific check performed.
- **Maps to:** `bugteam/PROMPTS.md` AUDIT spawn XML `<bug_categories>` — the return-or-verified-clean requirement.

### Test 5: Preservation failure test

Checks that FIX agents do not delete multi-caller helpers without mentioning them in findings.

- **Input:** FIX commit diffs (per-loop).
- **Procedure:** For each FIX commit, collect deleted lines. Cross-reference deletions against helper function definitions (functions >5 lines with multiple callers in the codebase). Check whether any deleted helper was not named in any finding from the preceding audit loop.
- **Fail condition:** A multi-caller helper was deleted or inlined and was not mentioned in the audit findings.
- **Fail message template:** `Commit <sha> removed/inlined <helper_name> which had <N> callers and was not named in the finding. The preservation constraint was violated.`
- **Pass condition:** No unexplained deletions of multi-caller helpers.
- **Maps to:** `bugteam/PROMPTS.md` FIX spawn XML `<constraints>` — the constraint on modifying only files referenced in `bugs_to_fix`.

## Eval baseline protocol

### Principle

Yesterday's session transcript is the baseline — no need to re-run it. The transcript already contains the full loop log. Extract metrics directly.

### How it works

1. **Baseline extraction.** From the candidate session with the targeted PR, extract: loop count, per-loop finding counts, per-loop scope violations (from step 2), verified-clean depth (from outcome XMLs), and any deleted helpers (from FIX commit diffs). Write to `self-improve-eval-data/<date>/baseline-<pr-number>.json`.

2. **Temp skill creation.** Write the target skill file's baseline content (fetched via `mcp__plugin_github_github__get_file_contents` at `refs/heads/main`) to a temp copy: `<file>.temp-<feature>`. Apply the proposed improvement to the temp copy. The production skill is not modified.

3. **Constraint-effectiveness evaluation.** Use `mcp__plugin_github_github__pull_request_read(method="get_diff", ...)` to read the PR's diff. Apply the three enforceability gates (actionable, verifiable, negative scope) from Step 6. A metric scores "Prevented" only when all three gates pass. Write to `self-improve-eval-data/<date>/test-run-<pr-number>-<feature>.json`.

4. **Comparison table.** Compute which metrics the improvement would have prevented. Promote when ≥2 metrics are "Prevented".

### Metric comparison table

```
| Metric | Baseline | Projected with improvement | Verdict |
|--------|----------|---------------------------|---------|
| Loop count | <count> | Prevented / Not addressed | Improvement / Same |
| Finding regressions | <count> | Prevented / Not addressed | Improvement / Same |
| Scope violations | <count> | Prevented / Not addressed | Improvement / Same |
| Verified-clean depth | <score> | Prevented / Not addressed | Improvement / Same |
```

### Baseline JSON schema (`baseline-<pr-number>.json`)

```json
{
  "pr_number": 376,
  "starting_sha": "abc123...",
  "date": "2026-05-06",
  "loop_count": 3,
  "findings_per_loop": [{"loop": 1, "total": 5, "p0": 1, "p1": 2, "p2": 2},
    {"loop": 2, "total": 3, "p0": 0, "p1": 1, "p2": 2},
    {"loop": 3, "total": 0, "p0": 0, "p1": 0, "p2": 0}],
  "finding_regression_count": 1,
  "scope_violations": [],
  "verified_clean_depth_issues": [],
  "preservation_violations": [],
  "final_outcome": "converged"
}
```

## Constraints

- **Boundary.** Modifies only `bugteam/`, `pr-converge/`, `findbugs/`, `fixbugs/` skill files and `_shared/pr-loop/`. Does not modify its own skill file or trigger configuration.
- **Transcript reading discipline.** Do not read entire 100K+ line JSONL files before filtering. Check mtime first, grep for keywords, then read only the portions containing relevant markers.
- **Everything MCP is the primary filesystem tool.** Prefer `mcp__everything__` tools over `Get-ChildItem` or `ls` for finding session files.
- **Evidence threshold is non-negotiable.** A single occurrence is not actionable, no matter how egregious. Two distinct sessions with the same failure before acting.
- **Scheduling.** This skill defines the workflow. The trigger is configured externally via Claude Desktop scheduled tasks — the skill does not set up its own trigger.
- **Temp files.** Clean up temp skill files (`*.temp-*`) and eval data files after promotion or discard, except for the structured log files in `self-improve-eval-data/<date>/` which are preserved for audit trail.
- **Baseline eval-data.** The `self-improve-eval-data/` directory lives alongside this SKILL.md and stores baseline JSON files, test-run results, and structured logs. Each run creates a `<date>/` subdirectory.
- **One PR per run.** The skill produces at most one PR per invocation. If multiple improvements are promoted, they go into a single PR.
