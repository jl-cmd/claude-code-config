Audit [REPO/ARTIFACT] [TARGET ID] for **Category K only** (codebase conflicts — incomplete propagation). Skip A–J. Sub-bucket forced-exhaustion mode: Category K is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — including the BEFORE state of changed surfaces, so the agent can compare before vs after]
ID prefix: `find`.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**K1. Multi-site name renames**
- For every renamed symbol in the diff, search the broader codebase for references to the OLD name.
- Don't trust IDE rename — check imports, type annotations, error messages, log strings, comments, docs, test fixtures, JSON / YAML keys.
- Cross-language references (e.g., a Python class name referenced in a TypeScript type definition).

**K2. Duplicated constants / defaults**
- Every literal value changed in this diff — search for the OLD value in sibling files.
- Numeric defaults duplicated across language boundaries (config.py + .ps1 + .yml).
- String defaults that double as user-facing labels and as keys.

**K3. Primary path vs fallback path**
- Every behavior changed in a primary path — verify the fallback / error / catch-all path produces consistent behavior.
- The PR #397 case: instruction text updated in primary skill-loaded branch; fallback `skill_reference` not updated.
- `try/except` blocks where the fallback returns a stale default that contradicts the new try-block behavior.

**K4. Feature flag / version gate consistency**
- Flag flipped — every `if FLAG:` and `if not FLAG:` site updated?
- Version gate bumped — every `if version >= X:` consistent across the codebase?
- Deprecation: every consumer migrated, or every consumer documented as still valid?

**K5. Producer-vs-consumer type contracts**
- Function return type changed — every caller's annotation / unpacking pattern updated?
- API response shape changed — every client / SDK / parser updated?
- Iterator yield count changed — every `for a, b in iter` updated to `for a, b, c in iter`?

**K6. Code vs documentation sync**
- Every behavior change — does the surrounding docstring still describe the OLD behavior?
- README / ADR / changelog — updated?
- Inline comments that contradict the new code.

**K7. Code vs test sync**
- Every behavior change — every existing test still passes for the right reason (not just because it was loose enough)?
- Negative tests still cover the new failure modes?
- Test fixtures / mocks reflect the new shape?

**K8. Cross-file / cross-language contract sync**
- Same value in multiple languages — both sides updated?
- Schema definitions in TypeScript + protobuf + JSON — all consistent?
- CSS class name in stylesheet + JSX + tests — all consistent?

**K9. Schema / data-shape propagation**
- Column added / removed / renamed — migration + model + serializer + tests + API docs?
- Enum variant added — every switch / match / mapping has a case?

## Cross-bucket questions to answer at the end

Q1: Is there a pattern in this diff where the primary site is updated but a parallel site (any sub-bucket) stays stale?
Q2: What's the worst contradiction introduced by this artifact — the one most likely to silently produce contradictory behavior at runtime? Cite [file:line] for both the changed and unchanged sites.
Q3: Which renamed/changed surface has the most parallel sites in the codebase, and which of those sites is most likely to have been missed?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket [K1]–[KN], produce Shape A or Shape B (with ≥3 probes). Each Shape A finding must cite BOTH the diff line that was changed AND the parallel line that was missed — the conflict is between the two, not in either alone. Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 parallel sites that should have been updated alongside the diff — find them." Open Questions section. Read-only. No edits, no commits.

Note: Category K Shape A findings are unusual in that they always cite TWO line locations (the changed line and the unchanged-but-should-have-changed line). The `failure_mode` should describe the contradiction between the two states.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL DIFF — including BOTH the changed lines AND surrounding context that shows what stayed the same.]

[ALSO INCLUDE any unchanged files in the codebase that the agent must search for parallel sites. For a small repo, inline a project tree. For a large repo, identify the most likely affected files via `git grep <renamed-symbol>` or equivalent and inline those.]
