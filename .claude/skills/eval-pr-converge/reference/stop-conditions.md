# Stop Conditions

| Condition | Action |
|-----------|--------|
| Unresolved merge conflicts after `update_pull_request_branch` | Abort with "merge conflict — manual resolution needed" |
| `inline_lag_streak >= 3` | Abort with "inline API lag persistent — manual investigation needed" |
| `copilot_rejection_rounds > 3` | Abort with "Copilot rejection budget exhausted — manual review needed" |
| User interruption | Stop loop, note reason in log |
| Eval-mode mergeability bypass | Skip gate (c), report "mergeability skipped (eval mode)" |

## Hard Blocker Protocol

On hard blocker:
1. Log the blockage reason and the tick data
2. Do NOT schedule the next wakeup
3. Report to user with the blockage reason and suggested next steps
4. Exit with the stop condition as the return status
