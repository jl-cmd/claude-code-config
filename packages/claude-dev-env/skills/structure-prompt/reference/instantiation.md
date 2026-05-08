# Fill placeholders with real values

Some prompts ship as templates with placeholder tokens. The skill replaces those with concrete values pulled from the rubric, the companion artifact, or the user.

## Detection patterns

A placeholder is any bracketed token whose content reads as instructional rather than a literal name. Common shapes:

- `[REPO/ARTIFACT]`
- `[TARGET ID]`
- `[N]`
- `[ARTIFACT METADATA]`
- `[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]`
- `[List the supported …]`
- `[Declared minimum …]`
- `[file:line / paragraph]`
- `[A1]–[AN]`, `[B1]–[BN]`, etc.

## Procedure

1. Find every placeholder in the prompt.
2. For each placeholder, look up the value via [`research.md`](research.md).
3. Replace the placeholder with the real value.
4. For `[INLINE THE FULL ARTIFACT HERE]`, fetch the artifact's text (file content, diff, transcript) and inline it as fenced code blocks. Use each file's path as a `###` heading above its fenced block.

## When the rubric points at a sibling prompt

Rubric files often say "use category-X.md as the canonical worked example." When that happens:

1. Read the sibling prompt.
2. Copy the sibling's data body — the inlined artifact — into this prompt's data body.
3. Sharpen this prompt's sub-bucket bullets so they cite the identifiers in the data body that match this category's axes.
4. Keep the category-specific phrasing intact. Only the data body and the per-bucket bullets that reference data-body content change.

## Sub-buckets that have nothing to find in the data body

When the data body holds nothing that fits a particular sub-bucket (e.g., a SQL sub-bucket and a diff with no SQL), that sub-bucket stays as a proof-of-absence shape. Spell out three adversarial probes the agent runs to confirm zero relevant content. Use the sub-bucket bullets to name the things the agent searches for.

## What stays put

These elements pass through untouched:

- The mission's category name (e.g., "Category B only") — derived from the file name, not the artifact
- The per-category disposition statement
- The cross-bucket question structure (Q1, Q2, Q3 by name)
- The output spec's lead format (`Total: N (P0=N, P1=N, P2=N)`)
- The adversarial-pass count (3) and severity tier (P1) — handled by [`adversarial-tuning.md`](adversarial-tuning.md) when the noun needs sharpening
