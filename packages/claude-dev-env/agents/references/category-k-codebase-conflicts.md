# Category K — Codebase conflicts (incomplete propagation)

**What this category audits:** changes that update one site of a pattern but leave parallel sites stale, producing contradictory behavior between the new and old code paths. Common when a name is renamed in one file, a default is changed in one constant but duplicated as a literal elsewhere, a fallback path is updated but the primary path isn't (or vice versa), or a feature flag is flipped in one branch of conditional code but missed in others.

**Why this category is narrow but recurrent:** the change *itself* is internally consistent — the diff looks correct in isolation. The bug only surfaces when you compare the diff against the *unchanged* parts of the codebase that share a contract with what was changed. Linters and unit tests rarely catch these; reviewers only catch them by mentally cross-referencing the change against every parallel site.

**Canonical example:** [jl-cmd/claude-code-config PR #397, comment r3210166636](https://github.com/jl-cmd/claude-code-config/pull/397#discussion_r3210166636). The PR updated an instruction at line 137 to direct the model to use `AskUserQuestion` instead of bailing out with "I don't know." But the fallback `skill_reference` string at lines 123–127 in the same file *still* told the model to "reply 'I don't know'." Both strings interpolate into the same `reason` field, giving the model contradictory guidance — the exact escape hatch the PR was meant to close remained available through the unchanged path.

## Other typical patterns

- A function signature renamed in the definition; one of three call sites still uses the old kwarg name.
- A CSS class renamed in the stylesheet; templates still reference the old name.
- A config key renamed in `defaults.yml`; a fallback in the loader still reads the old key.
- A feature flag deprecated; one conditional branch still checks the old flag.
- An enum variant renamed; documentation, error messages, or test fixtures still reference the old name.
- A constant updated in one constants file; a duplicated literal remains in a sibling file.
- A type signature widened in the producer; a consumer's type annotation still claims the narrower type.
- A migration that adds a column; ORM model file gets the column but a raw-SQL migration query elsewhere doesn't.
- An API endpoint version bumped; the SDK in the same repo still hits the old version.
- A docstring updated to describe new behavior; the implementation still does the old thing (or the reverse).

**Companion reference:** see `source-material-section-types.md`.

---

## Sub-bucket decomposition (Category K)

Decomposition is by the **kind of parallel site** that needs to stay in sync with what the diff changed.

| ID | Axis name | Concrete checks |
|---|---|---|
| K1 | Multi-site name renames | A renamed symbol — every reference (call sites, imports, type annotations, error messages, docs, tests) updated? |
| K2 | Duplicated constants / defaults | A value changed in one source-of-truth — every duplicated literal in sibling files / cross-language partners updated? |
| K3 | Primary path vs fallback path | A behavior changed on the happy path — does the fallback / error path produce consistent behavior? |
| K4 | Feature flag / version gate consistency | A flag flipped or version bumped — every guard, conditional branch, and consumer checked? |
| K5 | Producer-vs-consumer type contracts | A producer's output shape changed — every consumer's expected shape still matches? |
| K6 | Code vs documentation sync | An implementation behavior changed — docstrings, README, ADRs, comments still describe the new behavior? |
| K7 | Code vs test sync | An implementation behavior changed — every test (positive, negative, edge) still expresses the right contract? |
| K8 | Cross-file / cross-language contract sync | A value or shape that lives in multiple languages or files (e.g., PowerShell + Python) — both sides reflect the change? |
| K9 | Schema / data-shape propagation | A schema field added/removed/renamed — migrations, ORM, serializers, fixtures, API docs all updated? |

Customize per-artifact: for a single-file change with no parallel sites, Category K reduces to "verify there are no parallel sites we missed." For a cross-cutting change (e.g., renaming a public API), Category K may need 8+ sub-buckets to enumerate every consumer surface.

---

## Reusable sample prompt template (Category K)

````
Audit [REPO/ARTIFACT] [TARGET ID] for **Category K only** (codebase conflicts — incomplete propagation). Skip A–J. Sub-bucket forced-exhaustion mode: Category K is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — including the BEFORE state of changed surfaces, so the agent can compare before vs after]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL DIFF — including BOTH the changed lines AND surrounding context that shows what stayed the same.]

[ALSO INCLUDE any unchanged files in the codebase that the agent must search for parallel sites. For a small repo, inline a project tree. For a large repo, identify the most likely affected files via `git grep <renamed-symbol>` or equivalent and inline those.]

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
````

## Why Category K matters as its own bucket

Categories A–J describe failure modes within a single change. Category K describes the failure mode that emerges *between* the change and what didn't change. A reviewer walking only A–J reads the diff and judges it on its own merits — they can miss K entirely because the diff is internally consistent. K forces the reviewer to read the unchanged code with the diff in hand and look for sites that *should* have been touched.

The PR #397 case demonstrates the cost of not running K: a security-related instruction (close the "I don't know" escape hatch) was correctly updated in the primary path but left wide open in the fallback, defeating the purpose of the change. The diff looked clean. Only by reading lines 123–127 *with* the new line 137 in mind could the contradiction surface.

For a literal worked example using PR #394, see `category-a-api-contracts.md`. Category K walks for that diff:
- K2: `[int]$AgeSeconds = 120` (PowerShell installer) duplicates `DEFAULT_AGE_SECONDS = 120` (`config/sweep_config.py`). Both files are new in the same PR, so there's no "stale parallel site" yet — but a future change to one without the other would land squarely in K2.
- K8: same as K2, framed as cross-language contract.
- K1, K3–K7, K9: not applicable to this PR (no renames, no schema changes, no feature flags). Verified clean.
