# Ground Rules

1. **No inline PR edits by the orchestrator.** The orchestrator (main
   session) only reads state, spawns agents, and schedules wakeups. All
   production edits go through subagents.

2. **State.json concurrency via lock files.** When multiple teammates
   could write `state.json` concurrently, use a lock file. The lock has a
   30-second stale-break timeout.

3. **Maximum 2 teammates.** To keep context manageable, never spawn more
   than 2 background teammates simultaneously.

4. **General-purpose babysitter pattern.** Background tick agents use
   `general-purpose` type so they have access to all tools including
   `Skill`, `Agent`, and `ScheduleWakeup`.

5. **ScheduleWakeup ownership.** Only the parent session (harness) may
   call `ScheduleWakeup`. Background agents cannot — their tool registry
   does not include it. If a background agent detects it's time to
   schedule, it signals the parent via completion message.
