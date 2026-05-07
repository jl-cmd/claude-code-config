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

**Primary search path:** `~/.claude/projects/*/*.jsonl`

- Enumerate directories under `~/.claude/projects/` using `-Force` (directories and files can be hidden or have restricted visibility — plain `Get-ChildItem` may return empty).
- For each project directory, list all `*.jsonl` files modified within the date window.
- Grep for markers before reading full content: `bugteam`, `pr-converge`, `loop <N> audit`, `/eval-bugteam`, `/eval-pr-converge`.

**Fallback if primary search returns empty:** Recursively scan `~/.claude/projects/` with `-Force -ErrorAction SilentlyContinue`, limiting depth to 3 levels. Project directories may have restricted visibility that suppresses plain `Get-ChildItem` output — `-Force` enumerates them regardless.

### Supporting data

- **Obsidian vault `sessions/`** — structured session reports with frontmatter fields `project`, `date`, `status`. Use for narrowing the search window (which project, which date range) before diving into raw JSONL transcripts. An available Obsidian MCP backend is preferred over raw filesystem access.
- **Git history on both repos** (claude-code-config, python-automation-eval) — commit SHAs, file lists, diffs, PR numbers
- **Plan files at `~/.claude/plans/*.md`** — may contain aggregated run summaries from prior eval sessions

## The Process

### Step 0: Resolve date window

Set `window_start = now - 24h`. All session transcript filtering uses this boundary. Append a flag for the final report showing the window.

### Step 1: Find candidate sessions

Search order — try each source until at least one candidate is found:

**Source A — Obsidian vault sessions (preferred for structured data):**

1. Search the Obsidian vault `sessions/` for notes with frontmatter `project` matching known eval/automation project names and `date` within the date window.
2. If found, read the session notes directly — they already contain structured loop logs, outcomes, and findings.
3. Use `mcp__obsidian__search_notes` with `searchFrontmatter: true` and query terms like `bugteam`, `pr-converge`, `eval-bugteam`.

**Source B — JSONL session transcripts (raw data):**

1. List project directories under `~/.claude/projects/` using `-Force` (directories may have hidden attributes that suppress plain listings).
2. For each directory, list `*.jsonl` files modified within the date window.
3. If no files found via the glob, try direct known-path probes for each project name you know about (see Data sources section for patterns).
4. For each candidate file, grep for markers: `bugteam`, `pr-converge`, `loop audit`, `/eval-bugteam`, `/eval-pr-converge`.
5. Collect matched files into `candidate_sessions[]` with path, mtime, and matched markers.

**Source C — Plan files:**

1. Scan `~/.claude/plans/*.md` modified within the date window.
2. Grep for markers: `bugteam`, `pr-converge`, `eval-bugteam`, `eval-pr-converge`, `loop_count`.
3. Plan files may contain aggregated run summaries even when raw transcripts are unavailable.

If all sources return empty: refuse with "No bugteam/pr-converge sessions found in the last 24 hours."

### Step 2: Extract structured data per session

For each candidate session, read the transcript content. Extract:

- **PR number and repo**: from invocation context (e.g. "PR #384", repo URL, gh commands)
- **Starting SHA**: from step 2 loop state or initial context
- **Loop log**: per-loop finding counts, P0/P1/P2 breakdowns
- **Per-loop FIX commits**: commit SHAs from fix agent output (format "Fixed in <sha>")
- **bugs_to_fix file lists**: extracted from FIX agent prompts or outcome XMLs
- **Outcome XMLs**: if inline in the transcript, extract `<finding>` and `<verified_clean>` entries
- **Final outcome**: converged / cap reached / stuck / error
- **Changed files**: from diff discussions or final commit range

Store per-session metrics in a structured form (in-memory; write nothing to disk yet unless `--preserve-extractions` flag is set).

### Step 3: Run gap-detection tests

For each session with extracted data, run all 5 tests defined in the [Test reference](#test-reference) section below. Collect results:

- Per test, per session: `{test_name, session_path, result: "pass"|"fail", evidence, metric_values}`
- Apply the **evidence threshold**: a gap is confirmed only when the same test fails in 2+ distinct sessions (within or across the date window). Single failures are logged as "observed once, not yet confirmed" and suppressed from improvement output.
- Log single-occurrence failures to `self-improve-eval-data/<date>/single-occurrences.json`.

If no gaps are confirmed: refuse with "No actionable gaps found. Evidence threshold not met." Print the single-occurrence log path.

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

Before modifying production skill files, the improvement must be validated:

1. Identify an eval PR from the extracted data — a PR that had a full bugteam run in the date window with a known loop count, known finding regressions, and known final outcome. Record its starting SHA, PR number, and loop metrics as the **baseline**.
2. Create a temp copy of the target skill: for changes to `bugteam/SKILL.md`, create `bugteam-SKILL.md.temp-<feature>`. For changes to `_shared/pr-loop/fix-protocol.md`, create `fix-protocol.md.temp-<feature>`. Keep the production skill untouched.
3. Apply the improvement to the temp copy.
4. Run the temp skill against the same PR from the same starting SHA. This is the test run — it produces a fresh cycle under the proposed improvement.
5. Capture the same metrics from the test run:

| Metric | Baseline | Test run | Verdict |
|--------|----------|----------|---------|
| Loop count | (from extraction) | (from test run) | Improvement? |
| Finding regressions (increase between consecutive loops) | (from extraction) | (from test run) | Improvement? |
| Scope violations | (from extraction) | (from test run) | Improvement? |
| Verified-clean depth | (from extraction) | (from test run) | Improvement? |

### Step 7: Promote or discard

- **Promote:** If the test run outperforms the baseline on at least 2 metrics and is not worse on any metric, apply the improvement to the production skill file. Commit as a single commit.
- **Discard:** If metrics are unchanged or worse, remove the temp copy. Log the result to `self-improve-eval-data/<date>/discarded-improvements.json`.
- **Mixed signal:** If one metric improved and one regressed, log to `self-improve-eval-data/<date>/ambiguous-improvements.json` and skip promotion. Do not commit.

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

2. **Temp skill creation.** Apply the proposed improvement(s) to a temporary copy of the target skill file: `<file>.temp-<feature>`. The production skill is not modified.

3. **Temp skill execution.** Run the temp skill against the same PR from the same starting SHA. The starting SHA is recorded in the baseline. If the PR has advanced, find the exact commit from baseline and check out the worktree at that point.

4. **Capture test-run metrics.** Same metrics as baseline: loop count, per-loop finding counts, scope violations, verified-clean depth, helper deletions. Write to `self-improve-eval-data/<date>/test-run-<pr-number>-<feature>.json`.

5. **Comparison table.** Compute deltas. Promote only when ≥2 metrics improve and none regress.

### Metric comparison table

```
| Metric | Baseline | Test run | Verdict |
|--------|----------|----------|---------|
| Loop count | <N> | <N> | Improvement / Same / Worse |
| Finding regressions | <count> | <count> | Improvement / Same / Worse |
| Scope violations | <count> | <count> | Improvement / Same / Worse |
| Verified-clean depth | <score> | <score> | Improvement / Same / Worse |
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
- **Filesystem enumeration quirks.** `~/.claude/projects/` directories and their contents may have restricted visibility. Always use `-Force` for `Get-ChildItem` and `-Hidden` for equivalent Unix commands. If `Get-ChildItem` returns empty after `-Force`, use `Test-Path` on known subdirectory names as a direct probe.
- **Evidence threshold is non-negotiable.** A single occurrence is not actionable, no matter how egregious. Two distinct sessions with the same failure before acting.
- **Scheduling.** This skill defines the workflow. The trigger is configured externally via Claude Desktop scheduled tasks — the skill does not set up its own trigger.
- **Temp files.** Clean up temp skill files (`*.temp-*`) and eval data files after promotion or discard, except for the structured log files in `self-improve-eval-data/<date>/` which are preserved for audit trail.
- **Baseline eval-data.** The `self-improve-eval-data/` directory lives alongside this SKILL.md and stores baseline JSON files, test-run results, and structured logs. Each run creates a `<date>/` subdirectory.
- **One PR per run.** The skill produces at most one PR per invocation. If multiple improvements are promoted, they go into a single PR.
