# State Schema

| Field | Type | Description |
|-------|------|-------------|
| `round` | int | Current convergence round (1 = bugteam, 2 = copilot) |
| `round_1_clean_at` | SHA | HEAD where ROUND 1 (bugteam) was clean |
| `round_2_clean_at` | SHA | HEAD where ROUND 2 (copilot) was clean |
| `active_bugteam_run` | bool | Whether eval-bugteam is currently running |
| `inline_lag_streak` | int | Consecutive inline-lag detections |
| `tick_count` | int | Total ticks executed |
| `copilot_rejection_rounds` | int | Copilot rejection count (eval mode) |
| `eval_mode_mergeability_bypassed` | bool | Mergeability check skipped (eval) |
| `pre_copilot_lint_at` | SHA | HEAD where pre-Copilot lint was clean |
