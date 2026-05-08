# Category D — Variable scoping, ordering, and unbound references

**What this category audits:** closures, variable hoisting, declaration order, late binding in loops, name shadowing, conditional definition, mutable defaults — anything that can cause a name to bind to the wrong value (or to be unbound entirely) at the point of use.

**Examples of Category D findings:**
- A variable is referenced before assignment on one branch of an `if`/`else`.
- A loop closure captures the loop variable by reference where by-value capture is required.
- A name shadows an outer-scope variable the function still relies on.
- A mutable default argument (`def f(x=[])`) accumulates state across calls.
- A module-level import is conditionally executed and the symbol is unbound on some import paths.

**Companion reference:** see `source-material-section-types.md`.

---

## Sub-bucket decomposition (Category D)

| ID | Axis name | Concrete checks |
|---|---|---|
| D1 | Variable referenced before assignment on a branch | `UnboundLocalError` candidates; partial `try/except` where the target is set only in `try`. |
| D2 | Loop closure capture (by-ref vs by-value) | Lambdas / nested functions in a loop body that close over the loop variable. |
| D3 | Name shadowing of outer-scope symbols | A local name that shadows a builtin, module-level, or class-level symbol still in use. |
| D4 | Conditional definition leaving symbol undefined | `try/except ImportError` blocks; platform-conditional defs without fallbacks. |
| D5 | Mutable default arguments | `def f(x=[])`, `def f(x={})` — bound at definition, shared across calls. |
| D6 | Module-level circular imports / load order | Import-time side effects depending on partial-module state. |
| D7 | Async/sync ordering of side effects | `await` placed where a side effect should have already happened; out-of-order coroutine resolution. |
| D8 | Class-attribute vs instance-attribute confusion | `cls.x` vs `self.x`; attribute defined in `__init__` vs class body. |

---

## Reusable sample prompt template (Category D)

````
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
````

For a literal worked example using PR #394, see `category-a-api-contracts.md`. The Category D–relevant pieces of that diff: D1 (the `try: created = os.path.getctime(…) / except OSError: continue` block — `created` only bound inside `try`, but the `if now - created` is *inside* the try so no UnboundLocalError) and D2 (the `for each_directory_path, _, _ in os.walk(…)` — no closures inside, verified clean).
