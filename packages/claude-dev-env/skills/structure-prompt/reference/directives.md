# Performance directives → measurable constraints

Every performance directive in the optimized prompt maps to a measurable constraint or a specific scope.

## Detection patterns

Common performance directives:
- "Take a deep breath"
- "Think step by step" / "Let's think step by step"
- "You are an expert"
- "Be thorough"
- "Be comprehensive"
- "Be careful"
- "Do your best"
- "Please"
- "Kindly"

## Transformation

Each directive maps to a measurable constraint or to omission:

| Directive | Replacement |
|---|---|
| "Be thorough" | A surface enumeration. e.g., "Inspect: input validation, auth, secret handling." |
| "Be comprehensive" | A count target. e.g., "Produce at least 8 findings." |
| "Be careful" | A locator requirement. e.g., "Cite file:line for every claim." |
| "Take a deep breath" | omitted |
| "Please" / "Kindly" | omitted |
| "You are an expert" | omitted (covered by the mission line) |
| "Do your best" | omitted |

## Show-reasoning carve-out

"Think step by step" stays intact when the prompt explicitly requires the agent to show its reasoning chain in the output.
