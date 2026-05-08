Audit [REPO/ARTIFACT] [TARGET ID] for **Category I only** (concurrency hazards). Skip A–H, J–K. Sub-bucket forced-exhaustion mode: Category I is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — including: is this code single-threaded, threaded, asyncio, multiprocessing, or mixed?]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**I1. Shared mutable state without synchronization**
- Module-level lists / dicts / sets — mutated from multiple threads or coroutines?
- Class-level mutable defaults shared across instances.
- Singleton patterns under concurrent first-use.

**I2. Missing await on async operations**
- Every call to an `async def` — awaited?
- `asyncio.create_task(...)` — task reference held?
- Functions returning coroutines never awaited (silent no-op).

**I3. Lock ordering / deadlock potential**
- Multiple locks acquired in nested fashion — same order on every path?
- `with lock_a: with lock_b:` and elsewhere `with lock_b: with lock_a:` — deadlock.

**I4. Race conditions / TOCTOU**
- `os.path.exists(p)` then `open(p)` — file can be removed in between.
- `Test-Path X` then `Register-Y X` in PowerShell — state can change.
- Database read-then-write without `SELECT FOR UPDATE` or transaction.

**I5. Atomicity of compound operations**
- `dict[k] = dict.get(k, 0) + 1` — not atomic.
- File write-then-rename vs write-in-place.
- Counters incremented without `threading.Lock` or atomic ops.

**I6. Thread-local / async-local context bleed**
- `threading.local()` in thread pools — state leaks across reused threads.
- `contextvars.ContextVar` — does propagation cross `asyncio.create_task` boundaries as intended?

**I7. Cancellation handling**
- `asyncio.CancelledError` — caught and re-raised, or swallowed?
- Cleanup in `finally` blocks under cancellation.
- `asyncio.shield(...)` usage — protects intended scopes only?

**I8. Signal handling in multi-threaded code**
- Python: signals always handled on main thread regardless of which thread called.
- Handler installations in non-main threads silently no-op.

## Cross-bucket questions to answer at the end

Q1: Are there critical sections that span two sub-buckets (e.g., shared mutable state I1 plus a TOCTOU window I4)?
Q2: What's the worst race-condition hazard introduced by this artifact? Cite [file:line].
Q3: Where would a future change to introduce concurrency (e.g., adding a thread pool to what is currently a single-threaded loop) most likely break atomicity?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket [I1]–[IN], produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 race conditions across these [N] sub-buckets — find them." Open Questions section. Read-only. No edits, no commits.
