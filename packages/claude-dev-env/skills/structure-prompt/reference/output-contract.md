# Output contract

The skill emits exactly one artifact: the rewritten prompt. The emission shape depends on how the input arrived.

## Emission modes

**Paste mode** — input arrives as the user's message body or as a fenced block within it. Emit one fenced block containing the rewritten prompt:

````
```
<rewritten prompt>
```
````

**File-path mode** — input arrives as a file path argument (e.g., `/structure-prompt path/to/file.md`). Rewrite the file in place. Emit a one-line confirmation that names the file, gives the line-count delta, and lists the spokes that fired.

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

A second invocation of the skill on its own output produces the same output. The detection patterns in each spoke stop firing once their target shape has been applied — placeholders no longer match because they've been substituted; identifier mentions no longer match because citations have been added; the canonical sub-bucket no longer matches because the ⭐ marker is now present; the adversarial phrase no longer matches because the noun is specific.

## Authorized additions

The skill adds content only when a spoke explicitly authorizes it AND [`research.md`](research.md) confirms the new content matches a real source (rubric, sibling artifact, or user response). The authorized additions are:

- The mission line, when [`persona.md`](persona.md) replaces a role assignment
- The per-category disposition line, when [`per-category.md`](per-category.md) detects an unenforced framework
- Measurable criteria, when [`directives.md`](directives.md) or [`constraints.md`](constraints.md) replaces a soft directive
- Real values in place of placeholders, when [`instantiation.md`](instantiation.md) fires
- `file:line` citations on identifier mentions, when [`citation-depth.md`](citation-depth.md) fires
- The ⭐ canonical-case marker on one sub-bucket, when [`canonical-case.md`](canonical-case.md) fires
- A category-specific failure-mode noun in the adversarial-pass phrase, when [`adversarial-tuning.md`](adversarial-tuning.md) fires
- Surface-formatting normalization (typo correction, single bullet style, language tags on fenced blocks, trimmed trailing whitespace, collapsed blank-line runs, sequential heading levels), when [`cleanup.md`](cleanup.md) fires

Each addition needs evidence — a rubric line, a real line in the data body, or a user-supplied value via AskUserQuestion. When evidence is missing, the spoke leaves the prompt as-is and reports the gap in the file-mode confirmation or the paste-mode emission's footer.
