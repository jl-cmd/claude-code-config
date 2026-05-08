# Output contract

The skill emits exactly one artifact: the rewritten prompt as a single fenced block.

## Emission shape

````
```
<rewritten prompt>
```
````

## Preservation invariants

The rewritten prompt preserves byte-for-byte:
- Identifiers (variable names, function names, file paths)
- IDs and SHAs
- ID prefixes
- Proper names (people, products, services)
- Numeric values (line numbers, thresholds, counts)
- URLs
- Code block contents

## Idempotency

A second invocation of the skill on its own output produces the same output.

## Authorized additions

The skill adds content only when a spoke explicitly authorizes it. The authorized additions are:
- The mission line, when [`persona.md`](persona.md) replaces a role assignment
- The per-category disposition line, when [`per-category.md`](per-category.md) detects an unenforced framework
- Measurable criteria, when [`directives.md`](directives.md) or [`constraints.md`](constraints.md) replaces a soft directive

Every other transformation operates on existing input.
