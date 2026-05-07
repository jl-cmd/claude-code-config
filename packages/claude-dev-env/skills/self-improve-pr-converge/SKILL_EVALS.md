# Self-Improve PR Converge — Evaluation Suite

Evaluation-driven iteration set for the `self-improve-pr-converge` skill, following [Anthropic — Agent Skills best practices: evaluation and iteration](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration).

## Methodology

Evals are split into two layers. Both layers run against the same trace but carry different failure semantics.

**Layer A — Ironclad invariants.** Order-and-presence rules that MUST hold on every run regardless of fixture, regardless of the session transcripts available, regardless of which gaps are found. Citations use **section headings** — not fragile line numbers — so layout edits to `SKILL.md` do not invalidate the contract. If an assertion fails, either the run diverged from the skill or the cited text is ambiguous and needs patching.

**Layer B — Fixture-dependent expectations.** The concrete tool trace predicted for a specific fixture (known session transcripts, known gap-detection results, known eval PR). Layer B is prediction — reality may diverge in small ways (extra bookkeeping calls, different ordering of candidate session filtering) without indicating a skill defect. Layer B failures trigger reconciliation, not auto-failure.

**Cycle 0 status.** This document was drafted after the first real run on 2026-05-07 (see session 103). Observed trace data from that run is embedded in Evals 1-2. Evals 3+ remain predicted until exercised.

## Ironclad invariants (Layer A, apply to every eval)

| # | Invariant | Citation |
|---|---|---|
| I-1 | `mcp__everything__everything_search` is the exclusive file-finding mechanism. No `Get-ChildItem` or `ls` for session transcript discovery. | `SKILL.md` § **Data sources** — **Primary search via Everything MCP**; § **Constraints** — **Everything MCP is the primary filesystem tool** |
| I-2 | Candidate marker scanning uses `python scripts/scan_session_markers.py <paths...> --output <temp_path>`. No `Get-Content -match` or `Select-String` for JSONL scanning. | `SKILL.md` § **Step 1** — Source A step 3 |
| I-3 | Session-level transcripts exclude `\subagents\` paths. Only `<uuid>.jsonl` directly under a project directory qualify. | `SKILL.md` § **Step 1** — Source A step 2 |
| I-4 | Extraction uses `python scripts/extract_bugteam_metrics.py <sessions...>`. No inline regex-on-JSONL extraction. | `SKILL.md` § **Step 2** |
| I-5 | Evidence threshold: a gap is confirmed only when the same test fails in 2+ distinct sessions. Single failures are logged to `self-improve-eval-data/<date>/single-occurrences.json` and suppressed from improvement output. | `SKILL.md` § **Step 3**; § **Evidence threshold** |
| I-6 | Step 6 evaluation uses GitHub MCP tools exclusively (`mcp__plugin_github_github__get_file_contents`, `pull_request_read`, `get_commit`). No `git` or `gh` CLI operations. | `SKILL.md` § **Step 6** |
| I-7 | Promotion requires at least 2 of 4 metrics scored as "Prevented". | `SKILL.md` § **Step 7** |
| I-8 | Temp skill files (`*.temp-*`) are cleaned up after promotion or discard. Eval data in `self-improve-eval-data/<date>/` is preserved. | `SKILL.md` § **Constraints** — **Temp files** |
| I-9 | At most one PR created per invocation. Multiple promoted improvements go into a single PR. | `SKILL.md` § **Constraints** — **One PR per run** |
| I-10 | Refusal order: dirty tree refusal precedes no-sessions refusal, which precedes no-gaps refusal. First match wins. | `SKILL.md` § **When this skill applies** — **Refusals** |
| I-11 | Modifies only `bugteam/`, `pr-converge/`, `findbugs/`, `fixbugs/` skill files and `_shared/pr-loop/`. Does not modify its own skill file or trigger configuration. | `SKILL.md` § **Constraints** — **Boundary** |
| I-12 | The final report starts with `/self-improve-pr-converge exit:` and includes date window, sessions scanned, candidate count, tests run, confirmed gaps, and outcome. | `SKILL.md` § **Step 8** — **Final report format** |

Any eval failing one or more Layer A invariants fails the run.

## Observation strategy

Evals run in a harness that intercepts the tool layer:

- A **mock tool layer** records each MCP/Bash/PowerShell tool call with its arguments and returns synthetic responses matching the real tool's response shape. No real Everything MCP queries, no real GitHub API calls, no real file system writes.
- A **fixture directory** supplies canned JSONL session transcripts with known marker patterns, known finding counts, and known outcome XML content.
- **Assertions** run against the recorded call list.

The harness does not yet exist; this document defines its contract.

---

## Eval 1 — Happy path: gaps detected, improvement promoted

**Scenario.** Three candidate sessions exist in the date window: one with PR #374 (4 loops, L3→L4 FIX regression), one with PR #376 (4 loops, L1→L2 and L2→L3 FIX regressions, shallow verified-clean entries), and one with PR #101 (3 loops, L2→L3 FIX regression). Tests 1 and 4 both meet the 2-occurrence threshold. Cross-referencing confirms the FIX regression constraint is missing from `bugteam/PROMPTS.md`.

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-6, I-7, I-8, I-9, I-10, I-11, I-12.

**Layer B predicted trace (Cycle 0 observed, 2026-05-07).**

| # | Tool call | Source |
|---|---|---|
| 1 | `mcp__everything__everything_search(params={query: "jsonl", sort: "date-modified-desc", max_results: 200})` | `SKILL.md` § **Step 1** — step 1 |
| 2 | Client-side filter: `.claude\projects\` path containment, exclude `\subagents\` | `SKILL.md` § **Step 1** — step 2 |
| 3 | `Bash("cd ... && & 'venv/Scripts/python.exe' scan_session_markers.py <paths...> --output <temp>")` | `SKILL.md` § **Step 1** — step 3 |
| 4 | `Read(<temp_json>)` → review matched markers, then cleanup | `SKILL.md` § **Step 1** — step 3–4 |
| 5 | `Bash("cd ... && & 'venv/Scripts/python.exe' extract_bugteam_metrics.py <matched_sessions...>")` | `SKILL.md` § **Step 2** |
| 6 | `mcp__plugin_github_github__pull_request_read(method="get", owner="jl-cmd", repo="claude-code-config", pullNumber=376)` | `SKILL.md` § **Step 6** — step 5 |
| 7 | `mcp__plugin_github_github__pull_request_read(method="get_diff", owner="jl-cmd", repo="claude-code-config", pullNumber=376)` | `SKILL.md` § **Step 6** — step 5 |
| 8 | `mcp__plugin_github_github__get_file_contents(owner="jl-cmd", repo="claude-code-config", path="packages/claude-dev-env/skills/bugteam/PROMPTS.md", ref="refs/heads/main")` | `SKILL.md` § **Step 6** — step 2 |
| 9 | `Write(<file>.temp-<feature>, ...)` — temp copy of PROMPTS.md | `SKILL.md` § **Step 6** — step 3 |
| 10 | `Edit(<file>.temp-<feature>, ...)` — apply improvement | `SKILL.md` § **Step 6** — step 4 |
| 11 | `mcp__plugin_github_github__push_files(owner="jl-cmd", repo="claude-code-config", branch="feat/self-improve/...", files=[{path: "packages/claude-dev-env/skills/bugteam/PROMPTS.md", content: ...}], message=...)` | `SKILL.md` § **Step 8** |
| 12 | `mcp__plugin_github_github__create_pull_request(owner="jl-cmd", repo="claude-code-config", title="feat(self-improve): ...", head="feat/self-improve/...", base="main", draft=true, body=...)` | `SKILL.md` § **Step 8** |

**Pass criteria.**
- All Layer A invariants hold.
- Exactly one test_1_fix_regression gap confirmed (4 occurrences, ≥2 threshold).
- Exactly one test_4_verified_clean_depth gap confirmed (≥2 threshold).
- Cross-referencing against `bugteam/PROMPTS.md` finds Test 1 gap actionable, Test 4 gap actionable but scores 1/4 metrics.
- Promotion fires exactly once (Test 1: ≥2 metrics Prevented).
- Discard fires exactly once (Test 4: <2 metrics Prevented).
- Exactly one PR created (promotion).
- Final report matches `/self-improve-pr-converge exit: promoted`.

**Process check after next real run.** Trace may diverge:
- Extra `mcp__everything__everything_search` calls if pagination is needed.
- Extra `mcp__plugin_github_github__*` calls for additional PR data.
- Different gap confirmation counts depending on session transcript contents.
- If all 5 tests are running, test counts increase proportionally.

---

## Eval 2 — No sessions found

**Scenario.** `mcp__everything__everything_search` returns results, but after filtering to `.claude\projects\` and excluding `\subagents\`, zero files remain. Everything MCP and plan-file sources both return empty.

**Layer A invariants.** I-1, I-10.

**Layer B predicted trace.**

| # | Tool call | Source |
|---|---|---|
| 1 | `mcp__everything__everything_search(params={query: "jsonl", ...})` → 0 results | `SKILL.md` § **Step 1** |
| 2 | Zero candidates → skip marker scan, skip extraction | `SKILL.md` § **Step 1** |
| 3 | `mcp__everything__everything_find_recent(params={period: "24h", path: "~/.claude/plans", ...})` → 0 results | `SKILL.md` § **Step 1** — Source B |

**Pass criteria.**
- Assistant message matches `No bugteam/pr-converge sessions found in the last 24 hours.`
- Zero downstream tool calls after the search (no extraction, no MCP-GitHub calls, no PR).
- Final report contains `/self-improve-pr-converge exit: no-action`.

---

## Eval 3 — No gaps confirmed (below threshold)

**Scenario.** One candidate session exists with a single Test 1 or Test 4 failure. Extractor outputs one failure occurrence, but the evidence threshold (2+) is not met.

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-10, I-12.

**Layer B predicted trace.**

| # | Tool call | Source |
|---|---|---|
| 1 | `mcp__everything__everything_search` → results found | `SKILL.md` § **Step 1** |
| 2 | Marker scan → 1 session matched | `SKILL.md` § **Step 1** |
| 3 | Extraction script → 1 gap-detection failure | `SKILL.md` § **Step 2** |
| 4 | Gap tests → no test meets 2-occurrence threshold | `SKILL.md` § **Step 3** |

**Pass criteria.**
- Assistant message matches `No actionable gaps found. Evidence threshold not met.`
- Single-occurrence log written to `self-improve-eval-data/<date>/single-occurrences.json`.
- Zero MCP-GitHub calls, zero PR creation.
- Final report contains `/self-improve-pr-converge exit: no-action`.

---

## Eval 4 — Dirty tree in skill repo

**Scenario.** `git status --porcelain` in the `claude-code-config` worktree shows unstaged changes before the skill begins execution.

**Layer A invariants.** I-10.

**Pass criteria.**
- Assistant message matches `Uncommitted changes in claude-code-config. Stash or commit before running self-improve.`
- Zero tool calls beyond the initial status check.

---

## Eval 5 — Confirmed gap, already covered by existing text

**Scenario.** Two sessions show a Test 1 FIX regression failure. Cross-referencing against `bugteam/PROMPTS.md` reveals the NO_REGRESSION constraint already exists (e.g., from a prior self-improve cycle).

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-10, I-12.

**Layer B predicted trace.** Steps 1–5 identical to Eval 1, then:
- Step 4 cross-reference: reads PROMPTS.md, finds the constraint already covers the gap.
- Step 5: records the gap as "already-covered" in the report.
- Step 6–8: skipped (no improvement to evaluate).

**Pass criteria.**
- All Layer A invariants hold.
- Final report lists the gap with `→ already-covered`.
- `self-improve-eval-data/<date>/` has a single-occurrences log but no promotion or discard files.
- Zero temp skill files created.
- `/self-improve-pr-converge exit: no-action`.

---

## Eval 6 — Both tests pass (clean run)

**Scenario.** Three candidate sessions exist, but none show any gap-detection test failures. All tests pass with zero occurrences.

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-10, I-12.

**Pass criteria.**
- Gap-detection output shows all tests pass.
- No single-occurrence log written (zero failures).
- Zero MCP-GitHub calls, zero temp files, zero PR.
- `/self-improve-pr-converge exit: no-action`.

---

## Eval 7 — Mixed-signal evaluation (all 5 tests active)

**Scenario.** All 5 gap-detection tests are implemented. Tests 1 and 2 meet the threshold and are cross-referenced as actionable. Test 1 scores 3/4 Prevented, Test 2 scores 1/4 Prevented.

**Layer A invariants.** I-1, I-2, I-3, I-4, I-5, I-6, I-7, I-8, I-9, I-10, I-11, I-12.

**Layer B predicted trace.** Eval 1 steps 1–11 with 5 tests running instead of 2. Two cross-reference rounds, two temp copies, two evaluations.

**Pass criteria.**
- Test 1 promoted (3/4 Prevented ≥2 threshold).
- Test 2 discarded (1/4 Prevented <2 threshold).
- Exactly one PR containing only the Test 1 improvement.
- Discard logged to `self-improve-eval-data/<date>/discarded-improvements.json`.
- `/self-improve-pr-converge exit: promoted`.

---

## Eval 8 — Everything MCP returns 0 results, plan files succeed

**Scenario.** `mcp__everything__everything_search` returns no JSONL files. But `mcp__everything__everything_find_recent` finds plan files with bugteam markers.

**Layer A invariants.** I-10.

**Layer B predicted trace.**

| # | Tool call | Source |
|---|---|---|
| 1 | `mcp__everything__everything_search(params={query: "jsonl", ...})` → 0 | `SKILL.md` § **Step 1** — Source A |
| 2 | `mcp__everything__everything_find_recent(params={period: "24h", path: "~/.claude/plans", ...})` → results | `SKILL.md` § **Step 1** — Source B |
| 3 | Grep or read plan files for markers | `SKILL.md` § **Step 1** — Source B step 2 |

**Pass criteria.**
- Skill falls through to Source B (plan files) instead of refusing.
- At least one plan file read occurs.
- If plan files contain run data, extraction proceeds. If not, no-action exit.

---

## Eval 9 — MCP tools unavailable, refuses gracefully

**Scenario.** `mcp__plugin_github_github__pull_request_read` returns a permission-denied or connection error at Step 6.

**Layer A invariants.** I-6, I-10.

**Pass criteria.**
- Step 6 fails with clear error about MCP tool unavailability.
- Skill stops without modifying any production files.
- No temp files left behind.
- Report surfaces the MCP failure as the blocking issue.

---

## Iteration protocol

1. **Cycle 0 — Reconcile predictions with reality.** Compare every Layer B predicted trace against the observed trace on the next real run. Patch this file to match reality and annotate each correction with a reason. Cycle 0 reconciliation is already done for Eval 1 (observed 2026-05-07 against PR #376).

2. **Baseline.** Run every eval with the skill unloaded. Record which cases the base model handles from memory versus which it gets wrong.

3. **Treatment.** Run every eval with the skill loaded. Layer A invariants must pass on every case. Layer B mismatches trigger Cycle 0 reconciliation.

4. **Regress on change.** Every edit to normative text in `SKILL.md`, `scripts/extract_bugteam_metrics.py`, `scripts/scan_session_markers.py`, or `scripts/config/constants.py` re-runs the full suite. A passing→failing transition on any Layer A invariant blocks the change. A Layer B mismatch after such an edit triggers a patch to the affected eval trace in the same commit.

5. **Extend on gotcha.** When the skill misfires in real use, add a new eval that reproduces the miss before patching the orchestration or companion files.

## Harness sketch (future work)

A minimal Python harness under `scripts/evals/`:
- `harness.py` — loads a fixture, injects a mock tool layer that records calls and returns canned responses, invokes the lead with the trigger, collects the recorded trace, evaluates pass criteria.
- `fixtures/` — one subdirectory per eval with canned Everything MCP responses, canned JSONL transcripts, canned GitHub MCP responses, and the expected trace JSON.
- `run_evals.py` — discovery + pass/fail reporting, exits non-zero on any failure for CI.
- `invariants.py` — the Layer A assertion bank, imported by every fixture.

## Known structural gaps flagged during Cycle 0

1. **Tests 2, 3, 5 not implemented.** `extract_bugteam_metrics.py` `run_all_gap_tests()` only wraps tests 1 and 4. Tests 2 (scope violation), 3 (cross-file drift), and 5 (preservation failure) require commit-diff analysis that the extraction script does not perform. Until implemented, these test domains have zero coverage in the automated flow. The `run_all_gap_tests` function must be extended with `test_scope_violation`, `test_cross_file_drift`, and `test_preservation_failure` callers.

2. **Extraction script file-global constant count.** `ALL_SESSION_MARKERS` was added to `config/constants.py` to satisfy the CODE_RULES gate for the marker-scan script. If the extraction script gains new tests that share marker constants, consider whether the config boundary is correctly placed.

3. **`mcp__everything__` permission.** During Cycle 0, subagents required `mcp__everything__*` in `settings.json` permissions.allow. This was added as a permanent fix on 2026-05-07. Any new environment should verify this entry exists before running subagents.
