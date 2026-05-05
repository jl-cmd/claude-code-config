# ScheduleWakeup loop pacing (pr-converge)

Load this document for converge **loop pacing**. The pre-flight in `SKILL.md`
guarantees `ScheduleWakeup` is available before any tick runs. Shared bugbot
/ bugteam / Fix protocol steps stay in the main `SKILL.md`.

## Session behavior

Call `ScheduleWakeup` from this same session so the next tick fires back into **this** transcript with the prior tick's state line and PR
  context still addressable.

## Step 4 — `ScheduleWakeup` branch

At end of tick (unless convergence or another stop condition already omitted pacing), call `ScheduleWakeup` with:

- `delaySeconds: 270` whenever bugbot was just re-triggered (whether by Step 3 directly, by the Fix protocol's mandatory re-trigger, or by
  BUGTEAM branch 1's same-tick re-trigger). Bugbot finishes a review in 1–4 minutes, so 270s stays under the 5-minute prompt-cache TTL while
  giving a margin past bugbot's typical upper bound. The single exception is the BUGBOT inline-lag branch in Step 2 of the main skill, which
  uses `delaySeconds: 60` because no re-trigger fired and the only thing being awaited is GitHub's inline-comments API catching up.
- `reason`: one short sentence on what is being awaited, including the current `phase` and `bugbot_clean_at` SHA when set.
- `prompt: "/pr-converge"` — re-enters this skill on the next firing with default loop semantics (no need for the user to type `/loop`). If
  the parent harness requires the `/loop` wrapper for wakeups to execute, `prompt: "/loop /pr-converge"` is equivalent.

## BUGBOT inline-lag

When Step 2 BUGBOT branch c routes to API lag, complete Step 4 with
`ScheduleWakeup` using `delaySeconds: 60` (lag is short-lived).

## Convergence

On back-to-back clean: **omit** further `ScheduleWakeup` calls.

## Stop / safety

On hard blockers or user stop: omit `ScheduleWakeup` per main skill **Stop
conditions**.
