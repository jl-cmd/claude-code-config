# Narrative directives → measurable criteria

Every narrative directive in the optimized prompt names a measurable criterion.

## Detection patterns

A narrative directive opens with a soft verb:
- "Try to <X>"
- "Look at <X>"
- "Make sure to <X>"
- "Consider <X>"
- "Be sure to <X>"
- "Think about <X>"

## Transformation

Rewrite each narrative directive as a hard constraint with a measurable criterion.

| Narrative input | Constraint output |
|---|---|
| "Try to be concise" | "Output ≤ 200 words." |
| "Look at the security aspects" | "Inspect: input validation, auth checks, secret handling." |
| "Make sure to verify" | "Verify each claim against the source. Cite file:line." |
| "Consider edge cases" | "Enumerate: empty input, max-size input, concurrent input, malformed input." |
| "Think about performance" | "Report wall-clock cost and memory cost for each candidate." |

## Omission carve-out

When a narrative directive resists rewriting without inventing scope the original prompt did not authorize, omit the directive from the rewritten prompt AND emit a gap note that records both the omitted directive verbatim and the reason it could not be made measurable (e.g., `> Gap: Omitted directive "be thorough" — no measurable criterion authorized by the source.`). The gap note routes through the paste-mode or file-mode gap-report mechanism that [`output-contract.md`](output-contract.md) defines for the active emission mode. Silent omission is forbidden — see the [no silent no-op](output-contract.md#disposition-invariants) invariant.
