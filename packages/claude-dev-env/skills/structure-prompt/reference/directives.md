# Performance directives → measurable constraints

Every performance directive in the optimized prompt maps to a measurable constraint or a specific scope.

## Detection patterns

Common performance directives:
- "Take a deep breath"
- "Think step by step" / "Let's think step by step"
- "You are an expert"
- "Be thorough"
- "Be comprehensive"
- "Be careful" / "carefully"
- "Do your best"
- "Please"
- "Kindly"

## Transformation

Each directive maps to a measurable constraint or to omission:

| Directive | Replacement |
|---|---|
| "Be thorough" | A surface enumeration. e.g., "Inspect: input validation, auth, secret handling." |
| "Be comprehensive" | A count target. e.g., "Produce at least 8 findings." |
| "Be careful" / "carefully" | A locator requirement. e.g., "Cite file:line for every claim." |
| "Think step by step" / "Let's think step by step" | omitted |
| "Take a deep breath" | omitted |
| "Please" / "Kindly" | omitted |
| "You are an expert" | omitted (covered by the mission line) |
| "Do your best" | omitted |

## Show-reasoning carve-out

"Think step by step" stays intact when the prompt explicitly requires the agent to show its reasoning chain in the output. The carve-out MUST emit a gap note via the paste-mode or file-path-mode mechanism that [`output-contract.md`](output-contract.md) defines. See the [no silent no-op](output-contract.md#disposition-invariants) invariant.
