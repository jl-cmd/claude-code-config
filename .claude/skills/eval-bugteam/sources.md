# Sources

Verbatim doc quotes and URLs for the bugteam skill.

## A-J Category Rubric

Adapted from the bugteam category system used in production audits.
Categories A-J cover: API contracts, selectors/queries, resource cleanup,
variable scoping, dead code, silent failures, off-by-one, security,
concurrency, and magic values/config drift.

## Adversarial Pass Methodology

Each finding must include an adversarial "what does the obvious
remediation break?" pass. This prevents fix suggestions that would
introduce worse bugs than the original finding. Sources: bugteam gap
analysis from eval-baseline attempt 1.

## Gate-Output Cross-Reference

AUDIT subagents must read the captured gate output before making
hook-related predictions. Findings that contradict gate output are
forbidden. This rule was added after prior loops produced false-positive
audits that atomic-committed and blocked real fixes.

Source: eval-baseline attempt 3 findings.md.
