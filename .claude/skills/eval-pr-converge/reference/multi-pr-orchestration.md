# Multi-PR Orchestration

## Team Setup

| Role | Agent Type | Responsibility |
|------|------------|----------------|
| Orchestrator | Main session | Read state, spawn agents, schedule wakeups |
| Babysitter | `general-purpose` | Loops ticks on one PR, loads skills via `Skill` |
| Fix worker | `eval-clean-coder` | Apply fix-protocol, commit, push |

## Tick Flow (with state.json)

1. Orchestrator reads `state.json` to determine current phase
2. Orchestrator spawns babysitter for each PR in `all_prs`
3. Babysitter runs the tick per `per-tick.md`, loads skills via `Skill`
4. Fix worker commits and pushes per `fix-protocol.md`
5. Babysitter writes updated `state.json` and goes idle

## Concurrency Lock

Before reading or writing `state.json`, acquire a lock file:
- `<state_dir>/state.lock`
- Write PID + timestamp
- 30-second stale-break: if lock is older than 30s, break it
- Release after write

## Parallel PR Considerations

- Each PR gets its own `state.json` in `<state_dir>/pr-<N>/`
- Babysitter agents operate on one PR each
- Orchestrator collects results after all babysitters complete
