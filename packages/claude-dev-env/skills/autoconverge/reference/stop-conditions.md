# Stop conditions

The workflow ends one of two ways: converged (PR marked ready) or blocked. A
blocker exit returns `{ converged: false, rounds, finalSha, blocker }`, and the
skill still runs teardown (revoke permissions, final report).

## Blockers (end the run short of ready)

- **Copilot no-show** — Copilot surfaces no review on the current HEAD after
  three polls (360 seconds apart). `blocker` names the Copilot timeout.
- **Round cap** — 20 rounds pass without a full convergence-check pass. A
  convergence-check gate that no round can clear (for example a `mergeable_state`
  stuck at `blocked`, `behind`, or `unknown` that a rebase does not fix) reaches
  the cap this way. `blocker` reports the cap.

## Not a blocker (the run continues)

- **Bugbot down** — when Cursor Bugbot is opted out, or never produces a check
  run or review after the lens poll budget, the Bugbot lens returns `down: true`.
  The run continues, and the convergence check runs with `--bugbot-down` so its
  Bugbot gate is bypassed.
- **A lens agent dies** — when one parallel lens returns null (a terminal agent
  failure), the round proceeds on the surviving lenses. A real defect it would
  have caught surfaces in a later round or at the convergence check.

## User stop

Stopping the background workflow (`TaskStop`, or the user halting the run) ends
it where it stands. Re-launching `/autoconverge` starts a fresh run; the
workflow journal allows resuming the prior run from its last completed step with
`Workflow({ scriptPath, resumeFromRunId })`.
