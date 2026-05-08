# Category F — Silent failures

**What this category audits:** catch-all except clauses, unconditional success returns, errors logged then swallowed, default fallback values masking failure, async task error swallowing, boolean returns that produce the same value on success and failure, ignored return values from fallible calls, PowerShell `-ErrorAction SilentlyContinue` patterns that hide errors.

**Examples of Category F findings:**
- `except Exception: pass` swallows every error including programming bugs.
- A function returns `True` on the success path and `True` on every error path too.
- An async task error is logged while the caller continues as if it succeeded.
- `subprocess.run(...)` without `check=True` and the return code is never inspected.
- `Get-Command X -ErrorAction SilentlyContinue` followed by `.Source` access — the null is silently absorbed.

**Companion reference:** see `source-material-section-types.md`.

---

## Sub-bucket decomposition (Category F)

| ID | Axis name | Concrete checks |
|---|---|---|
| F1 | Catch-all except clauses | `except:` (bare), `except Exception:`, `except BaseException:` followed by `pass` / `continue` / log-only. |
| F2 | Errors logged then swallowed | `logger.error(...)` followed by `return None` / `return default` without re-raise. |
| F3 | Default fallback values masking failure | `dict.get(key, default)` where the absence of the key is itself a bug; `or default` short-circuits hiding `None`. |
| F4 | Async task error swallowing | `asyncio.create_task(...)` without exception observation; `gather(..., return_exceptions=True)` consumed loosely. |
| F5 | Boolean / status returns identical on success and failure | A function returns `True` on the happy path and `True` on the catch-all error path. |
| F6 | Ignored return values from fallible calls | `subprocess.run` without `check=True` and unchecked `returncode`; `os.write` return value discarded. |
| F7 | PowerShell error-suppression patterns | `-ErrorAction SilentlyContinue` followed by `.Property` access; `2>$null` or `*>$null`; `$?` not consulted. |
| F8 | Test-level swallowing | Tests that catch and log instead of asserting; `pytest.warns` used instead of `pytest.raises`. |

---

## Reusable sample prompt template (Category F)

````
Audit [REPO/ARTIFACT] [TARGET ID] for **Category F only** (silent failures). Skip A–E, G–K. Sub-bucket forced-exhaustion mode: Category F is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**F1. Catch-all except clauses**
- Every `except:` (bare) — name the specific exception types the caller actually raises.
- `except Exception: pass` — verify the suppressed errors are documented or harmless; otherwise narrow.
- `except BaseException:` — almost always wrong; KeyboardInterrupt / SystemExit should propagate.

**F2. Errors logged then swallowed**
- `logger.error/warning/exception(...)` followed by `return` / `continue` without re-raise.
- Stderr writes that double as error handling but don't surface failure to the caller.

**F3. Default fallback values masking failure**
- `dict.get(key, default)` where missing-key is bug-worthy.
- `getattr(obj, name, default)` where absence is a contract violation.
- `or default` short-circuits hiding `None` returns from upstream.

**F4. Async task error swallowing**
- `asyncio.create_task(...)` without `task.add_done_callback(...)` to surface exceptions.
- `await gather(*tasks, return_exceptions=True)` consumed via list iteration without `isinstance(r, Exception)` check.
- Background tasks fire-and-forget without observation.

**F5. Status returns identical on success and failure**
- Functions that return `True` (or `0`, or `None`) regardless of which branch ran.
- Functions whose return type is `Optional[X]` where the catch-all converts errors to `None`.

**F6. Ignored return values from fallible calls**
- `subprocess.run(...)` without `check=True` and `returncode` not inspected.
- `os.write` / `socket.send` return value not compared to length.
- HTTP responses where status_code is not checked.

**F7. PowerShell error-suppression patterns**
- `-ErrorAction SilentlyContinue` immediately followed by `.Source` / `.Name` access.
- `2>$null`, `*>$null` — verify the consumer doesn't depend on the suppressed output.
- Cmdlets in default error-action mode whose `$?` is never consulted.

**F8. Test-level swallowing**
- Tests with try/except that log instead of asserting.
- `pytest.warns` where `pytest.raises` should be used.

## Cross-bucket questions to answer at the end

Q1: Are there error paths that span two sub-buckets (e.g., an async task that swallows via F4, then has its result fed into a default-fallback per F3)?
Q2: What's the worst silent-failure hazard introduced by this artifact? Cite [file:line].
Q3: Where would a future error-handling refactor most likely *introduce* a silent failure (e.g., adding a try/except around code that previously crashed loudly)? Name the line(s).

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket [F1]–[FN], produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 silent failures across these [N] sub-buckets — find them." Open Questions section. Read-only. No edits, no commits.
````

For a literal worked example using PR #394, see `category-a-api-contracts.md`. Category F walks for that diff:
- F1: two `except OSError: pass` blocks at lines 26 and 32 in `sweep_empty_dirs.py` — first absorbs `getctime` failures (probably fine — file gone), second absorbs `rmdir` failures (silently skips non-empty dirs, no log).
- F7: `Get-Command py -ErrorAction SilentlyContinue` plus `.Source` access — the `if ($_py)` guard catches the null. But `Get-Command python` (fallback) lacks `-ErrorAction` — opposite F7 hazard (loud where silent was intended).
- F6: `Unregister-ScheduledTask -ErrorAction SilentlyContinue` — verify the script's intent on missing task.
