# Examples

## Both reviewers reviewed the same HEAD

Bugbot and Copilot both have reviews on `current_head`. Bugbot is clean,
Copilot dirty → apply fix-protocol for Copilot findings only.

## Inline lag detection

Bugbot review body says "found issues" but the inline API returns zero
comments matching the latest review. This is `inline_lag`, not `dirty`.
Bump streak, wait 90s, retry.

## Pre-Copilot lint pass catches issues

The lint pass finds eager-default evaluation in the diff. Apply
fix-protocol to fix, re-trigger bugbot, re-enter BUGBOT phase. The lint
finding is P1 (worth fixing before requesting review).

## Merge conflict encountered

PR shows `mergeable_state: "conflicting"`. Try `update_pull_request_branch`.
If that fails due to merge conflicts, log the divergent files and abort
with "merge conflict — manual resolution needed".

## Repeated Copilot rejection

Copilot has rejected 4 times. `copilot_rejection_rounds > 3` → abort with
"Copilot rejection budget exhausted — manual review needed".

## Eval-mode mergeability bypass

In eval mode, `eval_mode_mergeability_bypassed = true` → skip gate (c).
Report in final outcome: "mergeability skipped (eval mode)".
