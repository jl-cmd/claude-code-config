# Evaluation Mode

`BUGTEAM_EVAL_MODE=1` enables evaluation-specific behavior:

- **Eval-prefixed subagents.** Uses `eval-code-quality-agent` and
  `eval-clean-coder` instead of production `code-quality-agent` and
  `clean-coder`. These eval variants may run with different models or
  constraints.

- **Eval-data logging.** Per-session metrics are written to
  `eval-data/` directory at the project root for post-hoc analysis.

- **Copilot rejection tracking.** Tracks `copilot_rejection_rounds` in
  state to budget Copilot retries separately from bugteam loops.

- **P2-only early convergence.** When ALL findings in an audit loop are
  P2 (style/compliance only), the cycle exits without entering FIX.
  Style-only findings from hook-blocked or auto-addressed sources
  terminate the loop rather than cycling.
