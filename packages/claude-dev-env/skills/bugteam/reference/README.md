# Bugteam reference

Expanded material that used to live inline in `SKILL.md`. Load a file when the orchestration stub in `SKILL.md` is not enough — debugging GitHub review shape, gate semantics, teardown edge cases, or explaining the design to a human.

| File | Domain |
|------|--------|
| [`design-rationale.md`](design-rationale.md) | Why agent teams (clean-room), table-of-contents habit, when `/bugteam` applies, refusal reasons |
| [`team-setup.md`](team-setup.md) | Permissions grant (`CLAUDE_SKILL_DIR`), PR scope, `TeamCreate`, team name / sanitization / temp dir / roles / loop state |
| [`github-pr-reviews.md`](github-pr-reviews.md) | Per-loop reviews, `jq` + `gh api` payloads, anchors, fallbacks, REST endpoints |
| [`audit-and-teammates.md`](audit-and-teammates.md) | Pre-audit gate, full cycle numbering, AUDIT and FIX actions, parallel auditors |
| [`teardown-publish-permissions.md`](teardown-publish-permissions.md) | Utility scripts note, teardown, PR description rewrite, revoke, final report |

Canonical documentation quotes: [`../sources.md`](../sources.md).

## Retired: pre-push-review skill

The `pre-push-review` skill was retired in favor of the expanded code-rules enforcer gate and the `/qbug` skill.

The enforcer (`packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py`) now runs blocking and advisory checks covering all patterns the pre-push-review skill previously surfaced manually. Running `/qbug` before pushing replaces the old `Skill(pre-push-review)` invocation in every workflow that referenced it.

References updated:
- `skills/pr-review-responder/SKILL.md` — Rule 6 and checklist item updated to `/qbug`
- `commands/plan.md` — Phase 5 step 10 updated to `/qbug` gate
- `hooks/github-action/pre-push-review.yml` — deleted (workflow no longer needed)
- `hooks/github-action/test_workflow.py` — deleted alongside the workflow
