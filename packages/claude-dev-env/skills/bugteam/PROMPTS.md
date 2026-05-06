# Bugteam — spawn-prompt XML templates and outcome XML schemas

## AUDIT spawn-prompt XML (bugfind teammate)

Keep the spawn prompt self-contained: reference only the PR scope, audit rubric, and this loop number. Write each instruction as a standalone statement so the teammate reads the prompt as a fresh brief and every audit starts from first principles.

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head ref</branch>
  <base_branch>base ref</base_branch>
  <pr_url>full URL</pr_url>
  <loop>N</loop>
  <pr_number>N</pr_number>
  <worktree_path>absolute path from Step 1 per-PR workspace</worktree_path>
</context>

cd into `<worktree_path>` before any git, gh, or file operation.

<scope>
  <diff_path>Absolute path to the per-PR patch file: <run_temp_dir>/pr-<N>/loop-<L>.patch (same path as gh pr diff redirect in AUDIT)</diff_path>
  <scope_rule>Audit only lines added or modified in the diff. Pre-existing code on untouched lines is out of scope.</scope_rule>
</scope>

<bug_categories>
  Investigate each category explicitly. For each, return either at least
  one finding OR a verified-clean entry with the evidence used to clear it:
  A. API contract verification (signatures, return types, async/await correctness)
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
</constraints>

<posting>
  Posting is done via scripts under <script_dir>.
  Never write raw jq pipelines.

  1. Audit the diff against the 10 categories above. Buffer findings.
  2. Assign each finding a stable finding_id: `loopN-K`, K 1-based.
  3. Validate every finding's (file, line) against the captured diff.
     Unanchored findings → list in the review body under
     "### Findings without a diff anchor".
  4. Build the review summary markdown. Write to a temp file:

       ## /bugteam loop <N> Audit — Merged Findings
       **Total: N (P0=X, P1=Y, P2=Z)**

       ### Findings without a diff anchor
       (only if unanchored findings exist)
       - **[severity] title** — <file>:<line> — <one-line description>

     The review body is a summary header. Every anchored finding becomes
     its own review comment (step 6).

  5. For each anchored finding, write its body to a temp file:

       **[severity] title**
       Category: <letter>
       <description>
       File: <path>:<line>

  6. Post the review + finding comments via the script:

       python <script_dir>/post_audit_review.py \
         --owner <owner> --repo <repo> --number <number> \
         --commit-id "$(git rev-parse HEAD)" \
         --body-file <temp_review_summary.md> \
         --finding-file <temp_finding_1.md> --path <file> --line <N> \
         ...

     Capture review_url and comment ids/urls from stdout JSON.
     API reference: https://docs.github.com/en/rest/pulls/comments

  7. If the script exits non-zero, check stderr for a review URL.
     If present, the review summary was already posted — use that URL
     and list only the failed comment findings in a follow-up issue comment.
     If no review URL in stderr, fall back to a single issue comment:
       jq -Rs '{body: .}' < <temp_fallback.md> \
       | gh api repos/<owner>/<repo>/issues/<number>/comments -X POST --input -
     Include the review summary + all findings inline.
     Every finding gets used_fallback="true", finding_comment_url set
     to the issue-comment URL.

  8. Write outcome XML. Populate finding_comment_id and
     finding_comment_url from script output (or fallback URL).

  <script_dir> = absolute path to _shared/pr-loop/scripts/.
</posting>

<output_format>
  For the validator (-a): post findings via the script in <posting> above,
  then write the outcome XML below to .bugteam-pr<N>-loop<L>.outcomes.xml
  inside the PR's worktree directory (<worktree_path>).
  For sibling auditors (-b through -k): write outcome XML to
  <run_temp_dir>/pr-<N>/loop-<L>-<letter>.outcomes.xml (absolute path passed
  in prompt). YOU DO NOT POST TO GITHUB. Return only that path on stdout.
  The schema:
</output_format>
```

## AUDIT outcome XML schema (bugfind writes this)

```xml
<bugteam_audit loop="<N>" review_url="<url>">
  <finding
    finding_id="loop<N>-<index>"
    severity="P0|P1|P2"
    category="<letter>"
    file="<path>"
    line="<int>"
    finding_comment_id="<gh child comment id, or empty if unanchored/review-fallback>"
    finding_comment_url="<url of child comment, OR review_url if unanchored, OR fallback issue comment URL>"
    used_fallback="true|false"
  >
    <title>one-line title</title>
    <description>2-3 sentence description with concrete trace</description>
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
  <loop>N</loop>
  <pr_number>N</pr_number>
  <worktree_path>absolute path from Step 1 per-PR workspace</worktree_path>
</context>

cd into `<worktree_path>` before any git, gh, or file operation.

<bugs_to_fix>
  [for each P0/P1/P2 finding from last_findings:]
  <bug
    finding_id="loop<N>-<index>"
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
  2. Apply each fix you can address.
  3. Run `python -m py_compile` (or language-equivalent) on every modified file.
  4. git add by explicit path, then git commit with a message summarizing the bugs fixed.
     - If the commit fails because a git hook (pre-commit, commit-msg, etc.) blocked it,
       capture the hook's stderr, write status=hook_blocked for every finding in this loop
       (the commit was atomic; if it failed, no finding was applied), populate hook_output
       on each outcome, and return WITHOUT retrying. The lead will treat this loop as no-progress.
  5. git push with a plain fast-forward push (the default, no flag overrides).
  6. For each bug, post a fix reply to its finding_comment_id:
     - "Fixed in <commit_sha>" if the bug was addressed by your commit
     - "Could not address this loop: <one-line reason>" if you skipped or failed it
     - "Hook blocked the fix commit: <one-line summary>" if the commit was hook-blocked

     CLI shape for each reply (write the reply body to a temp file first):

       jq -Rs '{body: .}' < <tmp_reply.md> \
       | gh api repos/<owner>/<repo>/pulls/<number>/comments/<finding_comment_id>/replies -X POST --input -
  7. Write `.bugteam-pr<N>-loop<L>.outcomes.xml` inside `<worktree_path>` (schema below) and return its path.
</execution>

<outcome_xml_schema>
  <bugteam_fix loop="<N>" commit_sha="<sha or empty if no commit>">
    <outcome
      finding_id="loop<N>-<index>"
      status="fixed|could_not_address|hook_blocked"
      commit_sha="<sha if fixed, empty otherwise>"
      reply_comment_id="<id of the reply posted>"
      reply_comment_url="<url of the reply posted>"
    >
      <reason>only present when status=could_not_address; one-line reason text</reason>
      <hook_output>only present when status=hook_blocked; verbatim stderr from the blocked hook</hook_output>
    </outcome>
  </bugteam_fix>
</outcome_xml_schema>

<constraints>
  - Modify only files referenced in bugs_to_fix.
  - One commit on the existing branch, then push.
  - Keep the branch linear and the PR base fixed; append one new commit per
    loop and fast-forward push only.
  - Let every git hook run on every commit.
  - git add by explicit path — name each file being staged.
  - Preserve existing comments on lines you do not modify.
  - Type hints on every signature you touch.
</constraints>
```
