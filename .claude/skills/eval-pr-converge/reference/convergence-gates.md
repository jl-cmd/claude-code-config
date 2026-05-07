# Convergence Gates

Four sequential gates that must pass before marking a PR ready for review.

### Gate (a): Pre-Copilot Lint Pass

Run the 4-category lint pass: eager defaults, type-contract, log accuracy,
dict.get fallback. Fix any findings found. Record `pre_copilot_lint_at`.

**Pass:** All four categories clean → proceed to gate (b).
**Fail:** Findings surfaced → fix-protocol, re-trigger bugbot, re-enter BUGBOT phase.

### Gate (b): Copilot Findings Resolved

Request Copilot review. Fetch Copilot review on new HEAD. Inline findings
→ fix-protocol. Repeat until clean.

**Pass:** Copilot clean on current HEAD → proceed to gate (c).
**Fail:** Findings → fix-protocol, re-trigger bugbot, re-enter cycle.
Abort after `copilot_rejection_rounds > 3`.

### Gate (c): Mergeability

Check `mergeable_state`: if "dirty" or "behind", update branch via
`update_pull_request_branch`. If "conflicting" → rebase or manual conflict
resolution.

**Pass:** Clean mergeable state → proceed to gate (d).
**Fail:** Conflicts → attempt automated fix, else abort with reason.

### Gate (d): Post-Convergence Copilot

After mergeability fix, request one final Copilot review. Wait for result.
If clean → mark ready. If dirty → go back to gate (b).

**Pass:** All four gates passed → mark PR ready, omit loop pacing.
**Fail:** Dirty review → re-enter converge cycle.
