---
name: copilot-review
description: >-
  Babysits the GitHub Copilot reviewer on the current PR with a 5-minute
  self-wake loop. On each tick: fetches the latest copilot-pull-request-reviewer[bot]
  review, fixes unaddressed inline findings against the current HEAD (new commit,
  push, inline replies), then re-requests review via the documented
  requested_reviewers API. Triggers: '/copilot-review', 'watch copilot',
  'babysit copilot review', 'loop copilot reviews', 're-request copilot',
  'keep re-requesting copilot'.
---

# Copilot Review

Loops Copilot reviews on the current PR until it returns a clean review against the current HEAD.

## When this skill applies

The user is on a PR branch, wants Copilot (the GitHub Copilot reviewer bot) to keep re-reviewing after each push, and wants findings auto-addressed between ticks.

## The Process

### Step 1: Start the 5-minute loop

Invoke the `loop` skill with a 5-minute cadence. The looped prompt is the per-tick work in Step 2.

```
/loop 5m <per-tick instructions from Step 2>
```

Record the returned `job_id` so the user can stop the loop.

### Step 2: Per-tick work

On each tick, against the current PR (`gh pr view --json number,url,headRefOid,baseRefName`):

1. **Resolve HEAD.** Capture `headRefOid` — the current HEAD SHA.
2. **Fetch latest Copilot review.**

   ```bash
   gh api repos/OWNER/REPO/pulls/PR_NUMBER/reviews \
     --jq '[.[] | select(.user.login=="copilot-pull-request-reviewer[bot]")] | sort_by(.submitted_at) | last'
   ```

   Capture `commit_id`, `state`, `submitted_at`, and `id`.
3. **Decide the branch:**
   - **No review exists yet:** re-request (Step 3) and return. Copilot has not looked at the PR.
   - **Latest review's `commit_id` != current HEAD:** re-request (Step 3) and return. Copilot reviewed an older commit; prompt it to look at HEAD.
   - **Latest review's `commit_id` == current HEAD, state is `COMMENTED` or `CHANGES_REQUESTED` with unresolved inline comments:** fix the findings (Step 4), push, reply inline on each thread, then re-request (Step 3).
   - **Latest review's `commit_id` == current HEAD, clean (no unresolved inline findings, or state is `APPROVED`):** report clean and return. Do not re-request a clean HEAD review.
4. **Stop condition.** If the loop has produced a clean review against HEAD, tell the user and stop (`CronDelete <job_id>`). Otherwise the loop continues on its own.

### Step 3: Re-request Copilot

Use this exact command. The reviewer ID **must** be `copilot-pull-request-reviewer[bot]` with the `[bot]` suffix — empirically verified: `Copilot`, `copilot`, and `github-copilot` all return `requested_reviewers: []` with no error, so the API silently no-ops.

```bash
gh api -X POST repos/OWNER/REPO/pulls/PR_NUMBER/requested_reviewers \
  -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
```

### Step 4: Fix findings

For each unaddressed inline comment on the latest review:

1. Read the referenced file:line.
2. Write a failing test that reproduces the concern (TDD — skip only when the finding is a doc/comment nit with no behavior to test).
3. Implement the fix.
4. Commit on the existing branch (no amend, no force).
5. Push.
6. Reply inline on each comment thread via `gh api -X POST repos/OWNER/REPO/pulls/PR_NUMBER/comments` with `in_reply_to` set to the comment id, describing what changed and the new commit SHA.

Then proceed to Step 3 to re-request review against the new HEAD.

## Stopping the loop

- Clean review received → skill stops itself (`CronDelete <job_id>`).
- User says stop → run `CronDelete <job_id>` immediately.
- User lists active loops → `CronList`.

## Constraints

- **Never `--force`, `--amend`, or rebase.** Each tick appends commits.
- **Never `--no-verify`.** If a pre-push hook fails, diagnose and fix.
- **Draft PR state.** If the PR is ready-for-review, leave it alone. If the user wants it drafted before the loop, they must say so.
- **One tick = at most one fix commit.** Don't batch multiple review rounds into a single tick.
- **The `[bot]` suffix is load-bearing.** Every other spelling of the Copilot reviewer silently fails.

## Examples

<example>
User: `/copilot-review`
Claude: [reads PR, starts /loop 5m, returns job_id, reports "watching PR #123; tick every 5m"]
</example>

<example>
User: "babysit copilot on this PR until it's clean"
Claude: [same as above]
</example>

<example>
Tick fires, latest Copilot review is against an older commit.
Claude: [re-requests review, returns]
</example>

<example>
Tick fires, Copilot has 2 unaddressed inline findings on HEAD.
Claude: [TDD-fixes both, one commit, pushes, replies inline on both threads, re-requests review]
</example>

<example>
Tick fires, latest review is clean against HEAD.
Claude: [stops the loop via CronDelete, reports done]
</example>
