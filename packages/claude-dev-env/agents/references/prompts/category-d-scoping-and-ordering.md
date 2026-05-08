Audit [REPO/ARTIFACT] [TARGET ID] for **Category D only** (variable scoping, ordering, and unbound references). Skip A–C, E–K. Sub-bucket forced-exhaustion mode: Category D is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**D1. Variable referenced before assignment on a branch**
- Walk every `if`/`elif`/`else` chain — is every name read on an `else` branch also assigned on every preceding branch?
- `try/except` blocks that assign in `try` and read after the block.
- Variables defined inside a `for` loop and read after the loop with no else clause.

**D2. Loop closure capture**
- Lambdas defined inside a loop closing over the loop variable.
- Async tasks created in a loop with shared state.
- List/dict comprehensions that reference outer-scope names mutated in the loop.

**D3. Name shadowing of outer-scope symbols**
- A local parameter shadowing a builtin (`type`, `list`, `id`, `input`).
- A local variable shadowing an imported symbol still needed later in the function.
- Class methods shadowing parent-class methods unintentionally.

**D4. Conditional definition leaving symbol undefined**
- `try: import X / except: X = None` — does every use site handle `None`?
- Platform-conditional definitions (`if sys.platform == "win32": ...`) — are there fallbacks for other platforms?

**D5. Mutable default arguments**
- `def f(arg=[])`, `def f(arg={})`, `def f(arg=set())`.
- Class methods with mutable defaults shared across instances.

**D6. Module-level circular imports / load order**
- `from X import Y` cycles between modules.
- Import-time side effects (registering, caching) depending on partial-module state.

**D7. Async/sync ordering**
- `await` inserted between a check and an action that depended on the check.
- `asyncio.gather(*tasks)` where order of completion matters.
- Synchronous side effects performed inside async coroutines without awaiting their completion.

**D8. Class-attribute vs instance-attribute confusion**
- `cls.x` mutations affecting all instances.
- `self.x = []` in class body vs in `__init__`.

## Cross-bucket questions to answer at the end

Q1: Are there names that span two sub-buckets (e.g., a loop closure that also shadows an outer-scope symbol — both D2 and D3)?
Q2: What's the worst unbound-reference hazard introduced by this artifact? Cite [file:line].
Q3: Which symbol's binding context is most fragile to a future refactor that adds a new branch or moves an assignment? Name the line(s).

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket [D1]–[DN], produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 scoping bugs across these [N] sub-buckets — find them." Open Questions section. Read-only. No edits, no commits.
