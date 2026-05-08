Audit [REPO/ARTIFACT] [TARGET ID] for **Category G only** (off-by-one, bounds, integer overflow). Skip A–F, H–K. Sub-bucket forced-exhaustion mode: Category G is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**G1. Loop bounds**
- Every `range(...)` — verify start, stop, step against the iteration intent.
- `while i < n` vs `while i <= n` — which boundary does the body assume?
- Nested loops where inner depends on outer index.

**G2. Slice / substring indices**
- `s[i:j]` — `j` clamps at `len(s)`, but is the math `j = len(s)+1` ever reached?
- Negative indices: `s[-n:]` — what if `n > len(s)`?
- Off-by-one in `split` / `join` / `chunks`.

**G3. Array / list indexing with computed offsets**
- `arr[i + offset]` — bounds-checked?
- `arr[len(arr) - 1]` patterns — verify list non-empty.

**G4. Integer arithmetic overflow**
- 32-bit vs 64-bit: `[int]` in PowerShell overflows at 2^31; Python int is arbitrary precision.
- Time/duration math in milliseconds vs nanoseconds.
- Multiplication of two large values — does the product fit?

**G5. Floating-point comparison**
- `==` and `!=` between floats.
- `sum([0.1] * 10) == 1.0` — false in IEEE 754.
- Iterative accumulation comparing against a constant.

**G6. Date / time arithmetic**
- Timezone-naive vs aware comparisons.
- DST transitions (skipped/repeated hours).
- `time.time()` precision vs `time.monotonic()` / `time.perf_counter()`.
- Age threshold: `now - created >= min_age`.

**G7. Unicode codepoint vs byte length**
- `len(s)` in Python (codepoints) vs `len(s.encode('utf-8'))` (bytes).
- JavaScript `s.length` (UTF-16 code units, not codepoints).
- Go `len(s)` (bytes, not runes).

**G8. Threshold and age comparisons**
- `>=` vs `>` on numeric thresholds — does the boundary value fire?
- `>` on floating-point ages where precision can land exactly on the boundary.

## Cross-bucket questions to answer at the end

Q1: Are there bounds that span two sub-buckets (e.g., a loop bound G1 that depends on a slice index G2)?
Q2: What's the worst boundary hazard introduced by this artifact? Cite [file:line].
Q3: Which threshold or boundary is most fragile to a future change in input scale (e.g., from minute-scale to second-scale, or from KB to MB)?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket [G1]–[GN], produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 boundary bugs across these [N] sub-buckets — find them." Open Questions section. Read-only. No edits, no commits.
