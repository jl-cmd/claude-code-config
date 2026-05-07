# Bugteam -- spawn-prompt XML templates and outcome XML schemas

## AUDIT spawn-prompt XML (bugfind teammate)

Keep the spawn prompt self-contained: reference only the PR scope, audit rubric, and this loop number. Write each instruction as a standalone statement so the teammate reads the prompt as a fresh brief and every audit starts from first principles.

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head ref</branch>
  <base_branch>base ref</base_branch>
  <pr_url>full URL</pr_url>
  <round>R</round>
  <loop>L</loop>
  <pr_number>N</pr_number>
  <worktree_path>absolute path from Step 1 per-PR workspace</worktree_path>
</context>

cd into `<worktree_path>` before any git, gh, or file operation.

<scope>
  <diff_path>Absolute path to the per-PR patch file: <run_temp_dir>/pr-<N>/loop-<L>.patch (same path as gh pr diff redirect in AUDIT)</diff_path>
  <scope_rule>Audit only lines added or modified in the diff. Pre-existing code on untouched lines is out of scope.</scope_rule>
  <pr_body_path>Absolute path to the PR body markdown saved at <run_temp_dir>/pr-<N>/loop-<L>.body.md (lead writes this file before spawning AUDIT via `gh pr view <N> -R <owner>/<repo> --json body --jq .body`).</pr_body_path>
  <pr_body_rule>Read the PR body file. Cross-reference every claim, behavior description, or call-out in the body against the diff. When the body says "X behavior" but the diff implements Y, file a finding under category J (configuration/contract drift) citing the body line and the divergent diff hunk.</pr_body_rule>
  <changed_files_rule>Build the list of changed file paths from the diff. Open each one with Read and audit cross-file consistency: do all changed files agree on the new symbol names, function signatures, default parameters, exception types, and field names introduced by the diff? Same-pattern fixes must be applied consistently across every file in the diff. A finding in one file with the same defect pattern visible in a sibling file is a Cross-file-miss -- file a finding for the sibling.</changed_files_rule>
  <test_file_rule>Read every changed test file. Cross-reference test assertions, expected values, and mock setup against the production code's config constants and function signatures. When a test file asserts a value that diverges from config, file a finding under category J.</test_file_rule>
</scope>

<gate_output>
  Before reporting any finding that predicts hook-blocker behavior (comment removal, magic value flagged, naming gate, mypy, etc.), the lead has run code_rules_gate.py against the current diff and the gate's stdout/stderr is captured at <run_temp_dir>/pr-<N>/loop-<L>.gate.txt. Read that file before predicting what the enforcer will block. Do not assert "the enforcer will flag X" unless X appears in the captured gate output. Findings that contradict the captured gate output are forbidden -- they produced false-positive audits in prior loops that atomic-committed and blocked real fixes.
</gate_output>

<bug_categories>
  Investigate each category explicitly. For each, return either at least
  one finding OR a verified-clean entry with the evidence used to clear it.
  A category is verified-clean only when one complete execution path through
  the changed code has been traced from entry to exit. Surface-level scanning
  is insufficient evidence. The evidence field must name the function and the
  path traced:
  A. API contract verification (signatures, return types, async/await correctness)
     - A.1 Type-contract vs runtime contract: when a parameter or return is
       typed `Optional[T]`, `Union[A, B]`, or `T | None`, audit the function
       body for whether every constituent of the type is actually handled.
       When the body assumes the non-`None` branch (subscript, attribute
       access, `min()`/`max()`, arithmetic, format substitution) and the
       function is reachable with `None` from any caller visible in the diff
       or via `git grep` of the symbol, file a finding asking the body to
       either narrow the parameter type to the runtime contract OR add an
       explicit `if x is None: raise ValueError(...)` guard at function
       entry. The finding holds even when the in-process call path is
       provably safe today -- a broader type signature than the runtime
       contract is itself the bug, because the signature lies to readers
       and to mypy.
  B. Selector / query / engine compatibility
  C. Resource cleanup and lifecycle (file handles, connections, processes, locks)
  D. Variable scoping, ordering, and unbound references
  E. Dead code: dead parameters, dead locals, dead imports, dead branches, dead returns, and unused imports
  F. Silent failures (catch-all excepts, unconditional success returns, missing error propagation)
  G. Off-by-one, bounds, and integer overflow
  H. Security boundaries (injection, path traversal, auth bypass, secret leakage)
  I. Concurrency hazards (race conditions, missing awaits, shared mutable state)
  J. Magic values and configuration drift
</bug_categories>

<constraints>
  - Read-only on source code: the audit does not modify any source file.
  - Cite file:line for every finding.
  - When the diff alone does not provide enough context to confirm a bug,
    list it under "Open questions" rather than assert it.
  - For every finding, run an adversarial fix-impact pass before posting it: ask "if a FIX agent applied the obvious remediation for this finding, what new defect would surface?" When the answer names a real regression (drain loop, infinite retry, broken caller, removed-comment hook block, exposed secret), include a recommended_fix_constraint in the finding body that fences off that regression. Findings whose obvious remediation would introduce a worse bug are downgraded to Open questions, not posted as P0/P1/P2.
  - Cross-reference the captured gate output (<run_temp_dir>/pr-<N>/loop-<L>.gate.txt) for every hook-related claim. Do not invent enforcer behavior.
  - Cross-reference the PR body (<run_temp_dir>/pr-<N>/loop-<L>.body.md) for divergence between stated behavior and shipped behavior -- these are the findings reviewers like Copilot catch that diff-only audits structurally miss.
  - For every finding, search `git grep` for all callers of the targeted function. When the obvious fix would silently change behavior for other call paths, include a fix constraint that preserves them.
</constraints>

<comment_posting>
  1. Audit the diff against the 10 categories above. Buffer the findings
     in memory; all posting happens at step 6 once anchors are validated.
  2. Assign each finding a stable finding_id of exactly the form `loop<L>-<K>`
     where <K> is 1-based within this loop.
  3. Validate every finding's (file, line) against the captured diff. Split
     findings into two buckets: anchored (line is in the diff) and
     unanchored (line is not in the diff -- goes into the review body's
     "Findings without a diff anchor" section per Step 2.5).
  4. Build the review body per Step 2.5's review-body shape, filling in the
     P0/P1/P2 counts and the unanchored-findings list (if any). Format each
     finding body as:

       **[severity] one-line title**
       Category: <letter> (<category name>)
       <2-3 sentence description with concrete trace>

       _From /eval-bugteam audit loop <L>._

  5. Build the `comments` array: one object per anchored finding with
     `{path, line, side: "RIGHT", body}` (multi-line findings add
     `start_line, start_side: "RIGHT"`).
  6. Post ONE review via `pull_request_review_write(method="create",
     event="COMMENT", body=<review_body>, owner=<O>, repo=<R>,
     pullNumber=<N>, comments=[...])`. See Step 2.5 in SKILL.md for the full
     parameter shape. Harvest the parent review `html_url` from the response
     and the `comments[]` child entries (each with its own `id` and `html_url`).
     Match child entries to anchored findings in index order.
  7. If the review POST fails, use `add_issue_comment(owner=<O>, repo=<R>,
     issue_number=<N>, body=<full_text>)` as fallback.
  Body text is passed directly as string parameters to the MCP tool calls --
  no temp files, no jq, no shell pipes.
</comment_posting>

<output_format>
  For the primary (-a) auditor: write the outcome XML below to .bugteam-pr<N>-loop<L>.outcomes.xml inside
  the PR's worktree directory (<worktree_path>). For sibling auditors (-b/-c): write to <run_temp_dir>/pr-<N>/loop-<L>-{b,c}.outcomes.xml (absolute path passed in prompt). Return only that path on stdout. The schema:
</output_format>
```

## AUDIT outcome XML schema (bugfind writes this)

```xml
<bugteam_audit loop="<L>" review_url="<url>">
  <finding
    finding_id="loop<L>-<K>"
    severity="P0|P1|P2"
    category="<letter>"
    file="<path>"
    line="<int>"
    finding_comment_id="<gh child comment id, or empty if unanchored/review-fallback>"
    finding_comment_url="<url of child comment, OR review_url if unanchored, OR fallback issue comment URL>"
    used_fallback="true|false"
    gate_output_consistent="true|false"
    pr_body_cross_ref="true|false"
    cross_file_pattern="true|false"
  >
    <title>one-line title</title>
    <description>2-3 sentence description with concrete trace</description>
    <recommended_fix_constraint>one-line fence-off describing the regression a naive fix would introduce, or empty when the obvious fix has no fenceable interaction</recommended_fix_constraint>
    <adversarial_pass>one-line answer to "what does the obvious remediation break?"; the value "no regression detected" means the adversarial pass cleared it</adversarial_pass>
  </finding>
  <verified_clean>
    <category letter="<letter>" name="<name>" evidence="brief evidence + cleared conclusion"/>
  </verified_clean>
</bugteam_audit>
```

After the teammate writes the XML and returns, the lead reads `.bugteam-pr<N>-loop<L>.outcomes.xml` from the PR's worktree directory with the `Read` tool, parses it, and populates `loop_comment_index` from `<finding>` elements.

## FIX spawn-prompt XML (bugfix teammate)

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head</branch>
  <base_branch>base</base_branch>
  <pr_url>url</pr_url>
  <loop>L</loop>
  <pr_number>N</pr_number>
  <worktree_path>absolute path from Step 1 per-PR workspace</worktree_path>
</context>

cd into `<worktree_path>` before any git, gh, or file operation.

<bugs_to_fix>
  [for each P0/P1/P2 finding from last_findings:]
  <bug
    finding_id="loop<L>-<K>"
    severity="P0|P1|P2"
    file="<path>"
    line="<int>"
    category="<letter>"
    finding_comment_id="<id>"
    finding_comment_url="<url>"
  >
    <description>...</description>
  </bug>
</bugs_to_fix>

<execution>
  1. Read each referenced file before editing.
  2. **Per-finding commits.** Process each finding in `bugs_to_fix` independently:
     a. Apply only that finding's fix.
     b. Run test verification on every file touched by this finding. Look for
        a sibling test file (`tests/test_<module>.py`, `<module>/tests/`, or
        any `test_*.py` / `*_test.py` in the file's directory subtree). If one
        exists, run `pytest <test_file> -q --tb=short 2>&1 || true`. If no test
        file exists, fall back to:
        `python -m py_compile <file_path>` for syntax verification.
     c. `git add` the explicit paths, then `git commit -m "fix(<scope>): <finding_id> -- <one-line>"`.
        - When the commit succeeds: capture the new SHA into `commit_sha_by_finding_id[<finding_id>]`. Status `fixed`.
        - When a git hook (pre-commit, commit-msg, no-deletion, mypy, etc.) blocks this commit: capture stderr verbatim, run `git reset --hard HEAD` to discard the staged change for this finding only, status `hook_blocked` with the captured stderr in `hook_output`. Continue to the next finding -- the next finding is NOT affected by this loop's hook block.
        - When `git reset --hard HEAD` itself fails or the workspace is left dirty after a discard, status the finding `could_not_address` with reason "discard failed" and stop the loop (the lead handles atomic-recovery).
     d. After every successful per-finding commit, run a post-fix verification grep against the file you edited: search for the substring(s) that prove the fix landed (the new function name, the new constant, the structural rewrite). When grep does not find evidence the change is on disk, status the finding `could_not_address` with reason "post-fix verification failed".
  3. After every finding has been processed, `git push` with a plain fast-forward push (the default, no flag overrides). The push contains every successful per-finding commit; hook-blocked findings are absent from the push and surface in their replies as `hook_blocked`.
  4. For each bug, post a fix reply to its `finding_comment_id` via
     `add_reply_to_pull_request_comment(commentId=<id>, body=<reply_text>,
     owner=<O>, repo=<R>, pullNumber=<N>)`:
     - "Fixed in <commit_sha>" when the bug was addressed (use the per-finding SHA from `commit_sha_by_finding_id`)
     - "Could not address this loop: <one-line reason>" when skipped or failed
     - "Hook blocked the fix commit: <one-line summary; stderr quoted in outcome XML>" when the per-finding commit was hook-blocked
     Body text is passed directly as string parameters -- no temp files, no jq, no shell pipes.
  5. Write `.bugteam-pr<N>-loop<L>.outcomes.xml` inside `<worktree_path>` (schema below) and return its path.
</execution>

<outcome_xml_schema>
  <bugteam_fix loop="<L>" final_pushed_head="<sha of HEAD after the single push, or empty when nothing was committed>">
    <outcome
      finding_id="loop<L>-<K>"
      status="fixed|unverified_fixed|could_not_address|hook_blocked"
      commit_sha="<per-finding commit sha when status=fixed, empty otherwise>"
      reply_comment_id="<id of the reply posted>"
      reply_comment_url="<url of the reply posted>"
      post_fix_grep_pattern="<regex or substring used to verify the fix landed when status=fixed, empty otherwise>"
      post_fix_grep_hits="<integer count of hits at the captured pattern, empty when not applicable>"
    >
      <reason>only present when status=could_not_address; one-line reason text</reason>
      <hook_output>only present when status=hook_blocked; verbatim stderr from the blocked hook</hook_output>
    </outcome>
  </bugteam_fix>
</outcome_xml_schema>

<constraints>
  - Modify only files referenced in bugs_to_fix.
  - One commit per finding; one push at the end of the loop covering every successful per-finding commit.
  - Keep the branch linear and the PR base fixed; append one new commit per finding and fast-forward push only.
  - Let every git hook run on every commit.
  - git add by explicit path -- name each file being staged.
  - Preserve existing comments on lines you do not modify.
  - Type hints on every signature you touch.
  - Run a post-fix grep after each successful per-finding commit. When grep cannot find the substring/regex that proves the fix landed, mark the finding `could_not_address` instead of `fixed`.
  - **Narrow scope.** Fix only the exact defect at the specified file:line. No restructuring, no inlining helpers, no renames, no "while I'm here" cleanup.
  - **Scope-lock:** Change the exact line(s) specified in the finding. Do not
    modify any code outside the finding's file:line range. Do not refactor,
    rename, or restructure code beyond the minimal change needed. Every scope
    creep edit (changing unrelated guards, log levels, or search parameters)
    becomes a self-inflicted regression that requires its own fix loop.
  - **Preserve helpers.** Do not remove or inline existing helper functions unless the finding explicitly names the helper as the problem.
</constraints>
```
