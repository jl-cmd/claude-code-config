# State Schema (Multi-PR Mode)

Used by `state.json` for multi-PR orchestration sessions.

| Field | Type | Description |
|-------|------|-------------|
| `last_action` | string | `fresh`, `audited`, `fixed` |
| `last_findings` | object | `{total: int}` from last audit |
| `round` | int | Current convergence round (1 = bugteam, 2 = copilot) |
| `loop_count` | int | Number of audit-fix loops in current round |
| `active_bugteam_run` | bool | Whether a bugteam run is in progress |
| `bugbot_clean_at` | string (SHA) | Last commit SHA where bugbot was clean |
| `eval_bugteam_clean_at` | string (SHA) | Last commit SHA where eval-bugteam was clean |
| `copilot_clean_at` | string (SHA) | Last commit SHA where Copilot was clean |
| `tick_count` | int | Total ticks executed |
| `inline_lag_streak` | int | Consecutive inline-lag detections |
| `copilot_rejection_rounds` | int | Copilot rejection rounds (eval mode) |
| `started_at` | ISO-8601 | When the session started |
| `last_updated` | ISO-8601 | Last state update |
| `status` | string | `running`, `converged`, `stuck`, `capped`, `error` |
| `current_head` | string (SHA) | PR HEAD at last state write |

## Status Transitions

- `running` → `converged` (all three reviewers clean on same HEAD)
- `running` → `stuck` (FIX produced no new commits)
- `running` → `capped` (10 loops exceeded)
- `running` → `error` (preflight or gate failure)
