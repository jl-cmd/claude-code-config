# Background-agent second audit

Loaded on-demand from [`SKILL.md`](../SKILL.md) §Second-audit execution when `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS != 1` (team infrastructure absent — typical Cursor IDE sessions).

This path **replaces** agent teams with **simple background agents** — ordinary delegated workers (for example `general-purpose` with `run_in_background: true` where the host exposes that), **not** `TeamCreate` bugfind/bugfix teammates. The orchestrator **only spawns and waits**; it does **not** substitute for those agents by reading the diff, auditing files, or editing code inline.

Each background agent runs, inside its own session:

1. The same **preflight** and **code-rules gate** the bugteam lead runs before spawning bugfind: `bugteam_preflight.py` then `bugteam_code_rules_gate.py --base origin/<BASE>` from the packaged dev-env tree (`${CLAUDE_DEV_ENV_ROOT}` / `${CLAUDE_SKILL_DIR}` / repo docs as in bugteam `SKILL.md`). If scripts are not on disk, follow the repository's documented gate substitute (for example `.cursor/BUGBOT.md` where that file exists in the checkout).
2. **One** full second-audit pass over the PR scope: apply `CODE_RULES.md` and the bugteam audit rubric (`bugteam/reference/audit-contract.md`), producing either **convergence (zero findings)** or a **findings list with `file:line`** in the same shape `/bugteam` uses so Step **(c)** can branch unchanged.
3. Returns that outcome to the orchestrator as the handoff payload (the agent does **not** call `TeamCreate` or `Skill({skill: "bugteam", ...})`; it performs the equivalent work itself).

All later steps in this tick treat that outcome as **the second audit** where §(b)–(d) reference **bugteam** semantics (pushes, convergence, findings).

Reporting: when marking converged, the one-line report uses **`bugteam CLEAN`** if the team path ran; use **`cursor audit CLEAN`** if the background-agent path ran.
