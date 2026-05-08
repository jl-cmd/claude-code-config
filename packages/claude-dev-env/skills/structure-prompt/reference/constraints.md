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

When a narrative directive resists rewriting without inventing scope the original prompt did not authorize, omit the directive entirely.
