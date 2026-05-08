# Category J — CODE_RULES.md compliance

**What this category audits:** the hook-enforced and rubric-enforced rules from `~/.claude/docs/CODE_RULES.md`. Every PR passes through `code_rules_enforcer.py` at write time; flagging Category J findings during audit prevents fix-loops that the gate would otherwise trigger after the fact.

**Examples of Category J findings:**
- A literal `60` appears in a production function body (magic value rule).
- A new `MAX_RETRIES = 3` declared at module scope outside `config/`.
- A parameter named `ctx` instead of `context` (abbreviation rule).
- A function that returns a value with no return-type annotation.
- A new `# explains the loop logic` comment added to production code.

**Companion reference:** see `source-material-section-types.md`.

---

## Sub-bucket decomposition (Category J)

| ID | Axis name | Concrete checks |
|---|---|---|
| J1 | Magic values in production function bodies | Literals other than `0`, `1`, `-1` inside production function bodies. Test files exempt. |
| J2 | String-template magic | f-strings whose structural literal text (paths, URLs, patterns) belongs in `config/`. |
| J3 | Constants location | Module-level `UPPER_SNAKE = ...` outside `config/` in production code. Exempt path families: `config/*`, `/migrations/`, `/workflow/`, `_tab.py`, `/states.py`, `/modules.py`, test files. |
| J4 | File-global use-count | A file-global constant referenced by fewer than two methods/functions/classes in the same file. |
| J5 | Abbreviations | `ctx`, `cfg`, `msg`, `btn`, `idx`, `cnt`, `elem`, `val`, `tmp`, `str`, `num`, `arr`, `obj`, `fn`, `cb`, `req`, `res`. (Loop counters `i`/`j`/`k` and `e` for exceptions are exempt.) |
| J6 | Vague names | `result`, `data`, `output`, `response`, `value`, `item`, `temp`, `info`, `stuff`, `thing`. Vague prefixes: `handle`, `process`, `manage`, `do`. |
| J7 | Type hints | Missing type annotation on a parameter or return; presence of `Any` or `# type: ignore`. |
| J8 | New inline comments | New `#` or `//` comments in production code added by this diff. (Existing comments are NEVER removed — Comment Preservation rule.) |
| J9 | Logging format | `log_*(f"...")` rather than `log_*("...", arg)`. |
| J10 | Imports inside functions | `import` statements placed inside function bodies. |
| J11 | sys.path.insert dedup | `sys.path.insert(0, X)` must be guarded by `if X not in sys.path:` (test files exempt). |
| J12 | Hardcoded user paths | String literals naming a specific user's home directory (`C:/Users/jon/...`, `/Users/alice/...`, `/home/bob/...`). Use `pathlib.Path.home()`. |

Test files (`test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*`, `conftest.py`, paths under `/tests/`) are exempt from Category J except where the rule explicitly applies (e.g., J11 on `sys.path.insert`).

---

## Reusable sample prompt template (Category J)

````
Audit [REPO/ARTIFACT] [TARGET ID] for **Category J only** (CODE_RULES.md compliance). Skip A–I, K. Sub-bucket forced-exhaustion mode: Category J is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**J1. Magic values in production function bodies**
- Every numeric literal other than `0`, `1`, `-1` in a production function body — flag and propose a named constant in `config/`.
- Test files exempt.

**J2. String-template magic**
- f-strings where the structural literal text (paths, URLs, command patterns) is the magic.
- Strip the interpolated `{...}` — if what remains is a path / URL / regex / format, that fragment belongs in `config/`.

**J3. Constants location**
- Every module-level `UPPER_SNAKE = ...` declaration outside `config/` in production code.
- Exempt path families: `config/*`, `/migrations/`, `/workflow/`, `_tab.py`, `/states.py`, `/modules.py`, test files.

**J4. File-global use-count**
- For every file-global constant outside `config/`, count its references in the same file.
- Single reference: move to `config/` and import as a local alias.
- Zero references: delete (dead code).

**J5. Abbreviations**
- Walk every parameter, local, attribute name. Flag any in the abbreviation list.
- Exception: single-letter loop counters (`i`/`j`/`k`) and `e` for exceptions.

**J6. Vague names**
- Flag any name from the vague list (`result`, `data`, `output`, etc.).
- Flag any function whose verb prefix is `handle` / `process` / `manage` / `do`.

**J7. Type hints**
- Every parameter typed?
- Every return typed?
- Any use of `Any` or `# type: ignore`?

**J8. New inline comments**
- Every `#` or `//` comment line added by this diff in production code — flag.
- Module-level docstrings, function docstrings, class docstrings are allowed.
- Test files exempt.
- Exempt comment markers: shebangs, `# type:`, `# noqa`, `# pylint:`, `# pragma:`, `// @ts-`, `// eslint-`, `// prettier-`, `/// `.

**J9. Logging format**
- `log_*(f"...")` patterns — must be `log_*("template with {}", arg)` per the rule.

**J10. Imports inside functions**
- Every `import` / `from ... import ...` statement — verify at module scope.
- Exception: documented circular-import workarounds.

**J11. sys.path.insert dedup**
- Every `sys.path.insert(0, X)` — guarded by `if X not in sys.path:`?
- Test files exempt.

**J12. Hardcoded user paths**
- Any string literal containing `C:/Users/<name>/...`, `/Users/<name>/...`, `/home/<name>/...`?
- Replace with `pathlib.Path.home()` or `os.path.expanduser('~')`.
- Exempt: test files, `config/*`, workflow registry paths, Django migrations, hook infrastructure.

## Cross-bucket questions to answer at the end

Q1: Are there constants that span two sub-buckets (e.g., a magic value J1 inside an f-string J2 — the same literal flagged twice)?
Q2: What's the worst CODE_RULES drift introduced by this artifact? Cite [file:line].
Q3: Which finding would the hook block at write time, vs. which would only be caught by audit (slipping past the hook's pattern)?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket [J1]–[JN], produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P2 CODE_RULES violations across these [N] sub-buckets — find them." Open Questions section. Read-only. No edits, no commits.

Note: most Category J findings are P2 (style / cleanup) since they don't affect runtime behavior; the adversarial-pass quota uses P2 here.
````

For a literal worked example using PR #394, see `category-a-api-contracts.md`. Category J walks for that diff:
- J1: literal `120` in `[int]$AgeSeconds = 120` — already centralized in `config/sweep_config.py:DEFAULT_AGE_SECONDS`. PowerShell side duplicates the value (cross-language drift, see Category K for the conflict-with-existing-code framing).
- J2: f-strings like `f"deleted: {each_directory_path}"` and `f"watching {arguments.root} every {arguments.interval}s"` — the surrounding literal text is descriptive output, not structural; not flagged.
- J3: `_SCRIPTS_DIR` in test file is exempt (test files).
- J7: every parameter and return is annotated; no `Any`, no `# type: ignore`.
- J8: only module-level docstrings; no inline comments added.
