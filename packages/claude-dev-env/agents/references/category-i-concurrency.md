# Category I — Concurrency hazards

**What this category audits:** race conditions, missing awaits, shared mutable state, lock ordering, atomicity of compound operations, cancellation handling, thread-local / async-local context bleed, signal handling in multi-threaded code.

**Examples of Category I findings:**
- Two coroutines append to the same list without synchronization.
- An `await` is missing on a critical-section operation, allowing other tasks to interleave.
- A lock is acquired in different orders on two code paths (deadlock potential).
- TOCTOU between `os.path.exists` and `os.open` in a directory another process can modify.
- A `threading.local` value leaking across thread-pool reuse.

**Companion reference:** see `source-material-section-types.md`.

---

## Sub-bucket decomposition (Category I)

| ID | Axis name | Concrete checks |
|---|---|---|
| I1 | Shared mutable state without synchronization | Module-level lists/dicts/sets mutated from multiple threads or coroutines. |
| I2 | Missing await on async operations | `coro()` discarded without `await`; functions returning coroutines never awaited. |
| I3 | Lock ordering / deadlock potential | Multiple locks acquired in different orders on different code paths. |
| I4 | Race conditions / TOCTOU | Check-then-use patterns with a window where state can change. |
| I5 | Atomicity of compound operations | Read-modify-write sequences without atomic primitives. |
| I6 | Thread-local / async-local context bleed | `threading.local` in pools; `contextvars` propagation across `asyncio.create_task`. |
| I7 | Cancellation handling | `asyncio.CancelledError` propagation; cleanup on cancel. |
| I8 | Signal handling in multi-threaded code | Signals always go to main thread in Python; assumptions about handler thread. |

---

## Reusable sample prompt template (Category I)

````
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
````

For a literal worked example using PR #394, see `category-a-api-contracts.md`. Category I walks for that diff:
- I4: TOCTOU between `os.walk` enumerating a directory and `os.path.getctime` / `os.rmdir` on the same path — another process could delete or repopulate the dir in the window. The `try/except OSError` handles the race correctly (Category F notes the same blocks for silent-failure concerns; here they're actually protective).
- I4 (PowerShell): `Test-Path $Target` followed by `Register-ScheduledTask` — directory could be deleted between the check and the registration. Low-impact since the schedule still registers.
- I1, I2, I3, I5–I8: not applicable — script is single-threaded synchronous Python with no asyncio, no shared mutable state across processes.
