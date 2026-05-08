Audit [REPO/ARTIFACT] [TARGET ID] for **Category E only** (dead code and unused imports). Skip A–D, F–K. Sub-bucket forced-exhaustion mode: Category E is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
ID prefix: `find`.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**E1. New imports without references**
- Every `import X` and `from X import Y` introduced by the diff — verify at least one reference in the file body.
- `__all__` re-exports — file is exempt; flag only if `__all__` is also added in this diff.
- `# noqa` or `TYPE_CHECKING` blocks — exempt; verify the marker is correct.

**E2. Functions / methods defined but never called**
- Each new helper function — search the diff and the broader project for call sites.
- New methods on existing classes — verify a caller exists.

**E3. Code after unconditional return / raise / exit**
- Statements after `return X`, `raise X`, `sys.exit(N)`, `os._exit(N)` at the same indentation level.
- After an unconditional `continue` or `break` inside a loop.

**E4. Always-true / always-false conditions**
- `if True:` / `if False:` / `if 1:` literals.
- Conditions that reduce to constants given other code in the diff (e.g., `if x:` where `x` is set unconditionally just above).

**E5. Unused parameters**
- Each function signature — every parameter appears at least once in the body (or is documented as a callback contract requirement).
- `*args` / `**kwargs` accepted but unused.

**E6. Removed-but-not-deleted symbol references**
- Names in this diff that reference symbols removed or renamed elsewhere.
- Backward-compatibility shims that should be deleted now per the project's rules.

**E7. Test fixtures / helpers defined but never used**
- pytest fixtures with no parameter consumers.
- Test data factories defined in this PR with no call sites.

**E8. Stub / placeholder code without TODO**
- `pass` / `...` bodies in non-abstract methods.
- `raise NotImplementedError` without a tracking issue or TODO explaining replacement.

## Cross-bucket questions to answer at the end

Q1: Are there imports unused locally but consumed by a re-export pattern in another file? Cite the cross-file pair.
Q2: What's the worst unused-code hazard? (E.g., a function whose deletion would silently break a caller in a non-Python language calling via gettattr.) Cite [file:line].
Q3: Which symbol most likely will *become* dead code after a near-future refactor (function whose only caller is itself slated for removal)?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket [E1]–[EN], produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P2 dead-code instances across these [N] sub-buckets — find them." Open Questions section. Read-only. No edits, no commits.

Note: most Category E findings are P2 (style / cleanup) unless the dead code masks an actual bug; the adversarial-pass quota uses P2 here.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]
