# ScheduleWakeup Loop

Run every tick in the parent harness session. Pacing is managed via
`ScheduleWakeup` calls.

## Delay Values

| Situation | delaySeconds | Reason |
|-----------|-------------|--------|
| Bugbot re-triggered | 270 | Bugbot finishes in 1-4 min; 270s stays under 5-min prompt-cache TTL |
| Inline-lag retry | 90 | Short wait for GitHub inline API propagation; no re-trigger |
| Post-fix (same tick) | 270 | Wait for bugbot to review the new commit |

## Convergence

When all gates pass:
- Do NOT schedule a wakeup
- Emit the `converged` status
- The user receives the final report and decides next action

## Inline-Lag

When inline-lag is detected (dirty body, zero matching inline rows at
current_head):
- Increment `inline_lag_streak`
- Schedule wakeup with `delaySeconds: 90`
- On next tick, re-fetch inline comments for the same HEAD
- On `inline_lag_streak >= 3`, abort as hard blocker

## Ownership

Only the main harness session (the one that received `/eval-pr-converge`)
may call `ScheduleWakeup`. Background subagents do not have this tool in
their registry and must signal the parent if scheduling is needed.
