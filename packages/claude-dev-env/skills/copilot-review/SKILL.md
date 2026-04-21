---
name: copilot-review
description: >-
  Spawns a background subagent that babysits the GitHub Copilot reviewer on the
  current PR. The subagent self-paces at ~5 minutes per tick, fetches the
  latest copilot-pull-request-reviewer[bot] review, fixes unaddressed inline
  findings against current HEAD (new commit, push, inline replies), and
  re-requests review via the documented requested_reviewers API. The subagent
  terminates on convergence (clean review against HEAD) and reports back.
  Triggers: '/copilot-review', 'watch copilot', 'babysit copilot review',
  'loop copilot reviews', 're-request copilot', 'keep re-requesting copilot'.
---

# Copilot Review

Delegates Copilot babysitting to a background subagent so the main session stays free. The subagent loops internally and closes itself on convergence.

## When this skill applies

The user is on a PR branch, wants Copilot (the GitHub Copilot reviewer bot) to keep re-reviewing after each push, and wants findings auto-addressed between ticks — but does not want the main conversation consumed by polling.

## The Process

### Step 1: Gather PR context

From the current repo:

```bash
gh pr view --json number,url,headRefOid,baseRefName,headRefName,isDraft
```

Capture `number`, `headRefOid`, owner/repo (from `url`), and branch name. Pass these to the subagent so it does not rediscover them.

### Step 2: Spawn the background subagent

Invoke the `Agent` tool with:

- `subagent_type: "general-purpose"`
- `run_in_background: true`
- `description: "Copilot review loop for PR #<N>"`
- `prompt`: the full instructions in **Step 3 (Subagent prompt template)**, with placeholders filled in from Step 1.

Record the returned agent ID. Tell the user:

- The subagent is running in the background.
- It will self-terminate on convergence.
- To stop early: user says "stop the copilot loop" and you call `TaskStop <agent_id>`.
- The main session is free; completion arrives as a notification.

Do **not** use `/loop` or `CronCreate` in the main session. The subagent owns its own cadence.

### Step 3: Subagent prompt template

Pass this verbatim to the subagent (substituting the bracketed values):

> You are babysitting the GitHub Copilot reviewer on PR **#[NUMBER]** at **[OWNER]/[REPO]** (branch `[BRANCH]`, current HEAD `[HEAD_SHA]`). Your job: keep the loop running until Copilot returns a clean review against the current HEAD, then stop.
>
> **Per-tick work** (do this now, then on each wakeup):
>
> 1. Resolve current HEAD: `gh api repos/[OWNER]/[REPO]/pulls/[NUMBER] --jq '.head.sha'`.
> 2. Fetch latest Copilot review:
>    ```bash
>    gh api repos/[OWNER]/[REPO]/pulls/[NUMBER]/reviews \
>      --jq '[.[] | select(.user.login=="copilot-pull-request-reviewer[bot]")] | sort_by(.submitted_at) | last'
>    ```
>    Capture `commit_id`, `state`, `submitted_at`, `id`.
> 3. Decide the branch:
>    - **No review exists:** re-request (step 4), schedule next wakeup, return.
>    - **Latest review's `commit_id` != current HEAD:** re-request (step 4), schedule next wakeup, return.
>    - **Latest review's `commit_id` == current HEAD with unresolved inline findings:** TDD-fix them, push, reply inline on each thread, re-request (step 4), schedule next wakeup, return.
>    - **Latest review's `commit_id` == current HEAD and clean:** report convergence to parent (one-sentence summary), **do not** schedule another wakeup. You are done.
> 4. Re-request Copilot. The reviewer ID **must** be `copilot-pull-request-reviewer[bot]` with the `[bot]` suffix — empirically verified: `Copilot`, `copilot`, and `github-copilot` all return `requested_reviewers: []` with no error, silently no-op.
>    ```bash
>    gh api -X POST repos/[OWNER]/[REPO]/pulls/[NUMBER]/requested_reviewers \
>      -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
>    ```
> 5. Schedule the next wakeup with `ScheduleWakeup`:
>    - `delaySeconds: 300`
>    - `reason`: one short sentence on what you are waiting for.
>    - `prompt`: the literal sentinel `<<autonomous-loop-dynamic>>` so the next firing re-enters these instructions.
>
> **Fix protocol** (step 3, third branch):
>
> - Read each referenced file:line.
> - Write a failing test first when the finding has behavior to test; skip only for pure doc/comment nits.
> - Implement the fix.
> - Commit on the existing branch. Never `--amend`, `--force`, `--no-verify`, or rebase.
> - Push.
> - Reply inline on each comment thread: `gh api -X POST repos/[OWNER]/[REPO]/pulls/[NUMBER]/comments` with `in_reply_to` set to the comment id, referencing the new commit SHA.
>
> **Stop conditions:**
>
> - Convergence (clean review against HEAD): report and terminate.
> - Unrecoverable error (push blocked by hook you cannot resolve, API auth failure, CI broken and you cannot fix it in one commit): report the blocker to the parent and terminate without scheduling another wakeup.
> - Parent sends `TaskStop`: terminate immediately.
>
> **Safety cap:** if you have run 20 ticks without convergence, stop and report — something is wrong with the loop.

### Step 4: Report back to the user

After spawning, tell the user in one or two lines: subagent ID, PR URL, that it will notify on convergence or blocker. Nothing else.

## Stopping the subagent

- Convergence → subagent stops itself.
- Blocker → subagent reports and stops.
- User says stop → `TaskStop <agent_id>`.
- User asks what loops are running → `TaskList`.

## Constraints (for the subagent)

- **Never `--force`, `--amend`, or rebase.** Each tick appends commits.
- **Never `--no-verify`.** If a pre-push hook fails, diagnose and fix.
- **Draft PR state.** If the PR is ready-for-review, leave it alone. If the user wants it drafted before the loop, they say so.
- **One tick = at most one fix commit.** Do not batch multiple review rounds into a single tick.
- **The `[bot]` suffix is load-bearing.** Every other spelling of the Copilot reviewer silently fails.

## Examples

<example>
User: `/copilot-review`
Claude: [reads PR context, spawns background subagent with the Step 3 template, reports "subagent X watching PR #123; will notify on convergence"]
</example>

<example>
User: "babysit copilot on this PR until it's clean"
Claude: [same as above]
</example>

<example>
Subagent tick fires, latest Copilot review is against an older commit.
Subagent: [re-requests review, schedules next wakeup, returns]
</example>

<example>
Subagent tick fires, Copilot has 2 unaddressed inline findings on HEAD.
Subagent: [TDD-fixes both, one commit, pushes, replies inline on both threads, re-requests review, schedules next wakeup]
</example>

<example>
Subagent tick fires, latest review is clean against HEAD.
Subagent: [reports convergence to parent, terminates — no further wakeups]
</example>
