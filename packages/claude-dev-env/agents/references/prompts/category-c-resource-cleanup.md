Audit [REPO/ARTIFACT] [TARGET ID] for **Category C only** (resource cleanup and lifecycle). Skip A, B, D–K. Sub-bucket forced-exhaustion mode: Category C is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**C1. File handles / file objects**
- Every `open()` call — is it inside a `with` block?
- Every explicit `.close()` — is it reachable on every code path including exceptions?
- Files passed across function boundaries — does ownership of close transfer cleanly?

**C2. Subprocess / child processes**
- `subprocess.Popen` calls — paired with `wait` / `communicate` / context manager?
- `subprocess.run` — naturally bounded, but verify no zombie processes via `start_new_session`.
- Process exit signal handling on parent termination.

**C3. Temporary files and directories**
- `tempfile.TemporaryDirectory()` — used as context manager?
- `tempfile.NamedTemporaryFile(delete=...)` — semantics understood for the platform?
- Cleanup on uncaught exception within the `with` body.

**C4. Network connections**
- HTTP clients (`requests.Session`, `httpx.Client`) — closed on every path?
- DB connections / engines / sessions — released back to pool?
- Sockets — closed even on exception during handshake?

**C5. Locks, semaphores, mutexes**
- Every `acquire()` paired with `release()` on every path; prefer `with lock:`.
- Thread vs async lock mixing.
- Lock held across `await` points (Category I overlap — flag here for cleanup-only concerns).

**C6. Subscriptions / event listeners / signal handlers**
- `signal.signal()` registrations — restored on shutdown?
- Event listeners (e.g., DOM, asyncio, observer pattern) — unregistered on disposal?
- Weakref vs strong-ref subscriptions — leaks?

**C7. Background threads / async tasks**
- `asyncio.create_task()` — task references kept (else GC may cancel)?
- `threading.Thread` — joined on shutdown?
- `asyncio.gather` — exception propagation; child task cleanup on parent cancel.

**C8. OS-level resources**
- File descriptors leaked via os.open without os.close?
- Named pipes / mmap / shared memory cleanup paths?

## Cross-bucket questions to answer at the end

Q1: Are there resources acquired in one sub-bucket but released by another (e.g., a lock acquired by C5 but released only when the file in C1 closes)?
Q2: What's the worst leak hazard introduced by this artifact? Cite [file:line].
Q3: Where would an exception thrown from inside a `try` block cause a resource to leak? Name the line(s) most fragile.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket [C1]–[CN], produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 leaks across these [N] sub-buckets — find them." Open Questions section. Read-only. No edits, no commits.
