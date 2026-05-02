# OS-scheduled loop (no `/loop`, no `ScheduleWakeup`)

Loaded on-demand from [`SKILL.md`](../SKILL.md) §Loop cycle without `/loop` or ScheduleWakeup when the host exposes **neither** primitive. There is still **no in-model timer**; the **only** substitute this skill defines is an **OS-level scheduled job** the operator installs once.

**Harness (normative):** use **cron** (Unix), **systemd timer** (Linux services), or **Windows Task Scheduler** to run on a **fixed wall-clock interval of 270 seconds** (same default as Step 4 `delaySeconds` — long enough for Bugbot, under typical cache TTL). Each run executes **exactly one** non-interactive agent invocation using the **product's documented** "single prompt from file / stdin" CLI or API entrypoint. The job's input is a **constant** one-tick instruction: run §Per-tick work for the target PR; read prior state from disk; write updated state to disk; exit zero on success.

**State on disk (required for this harness):** prior tick output must live where the next run can read it without chat history — for multi-PR use `<TMPDIR>/pr-converge-<session_id>/state.json` (§Per-PR state file); for a single PR without that file, the operator picks **one absolute path** to a small JSON file, passes it to every run (argument or environment), creates it on the first tick, and updates it every tick. The scheduled command must wire that path into the frozen prompt or process environment the agent reads.

**Enforceability:** the OS records whether each run started and its exit code (cron logs, `journalctl`, Task Scheduler **Last Run Result**). A missed tick or failing process is visible to operators; the model cannot "silently skip" the schedule.

**Step 4 in these hosts:** `ScheduleWakeup` calls are **omitted**; the **next** tick is whichever **scheduled OS run** fires next. Do not delegate re-entry to a background subagent calling `ScheduleWakeup` on hosts where that tool does not exist (see `SKILL.md` §Why the work runs in the main session).
