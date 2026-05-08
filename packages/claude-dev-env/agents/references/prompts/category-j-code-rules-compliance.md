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
