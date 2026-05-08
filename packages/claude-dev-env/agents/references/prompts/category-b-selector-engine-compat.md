Audit [REPO/ARTIFACT] [TARGET ID] for **Category B only** (selector / query / engine compatibility). Skip A, C–K. Sub-bucket forced-exhaustion mode: Category B is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch. See ../source-material-section-types.md for chunking guidance.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**B1. CSS / DOM selector vs target browser engine**
- [List the supported browser/engine matrix from your project's compat target.]
- Pseudo-classes used and their support status across that matrix.
- Selector specificity assumptions that depend on engine quirks.

**B2. SQL syntax vs database version**
- [Declared minimum DB version + dialect.]
- Window functions, CTEs, JSON ops, dialect-specific functions used in the diff.
- Migration syntax compatibility with both old and new schema versions.

**B3. Regex syntax vs engine flavor**
- Engine in use ([Python re / PCRE / RE2 / JS / POSIX ERE]).
- Lookbehind/lookahead, named groups, backreferences, Unicode character classes.
- Patterns built with f-strings — does the interpolated content escape regex metacharacters when needed?

**B4. Shell / CLI / cmdlet syntax vs runtime version**
- [Declared minimum runtime versions.]
- Cmdlet parameters / CLI flags introduced after the minimum version.
- Bash-isms in /bin/sh-targeted scripts, or PS 7-isms in 5.1-targeted scripts.

**B5. JSON path / XPath / structural query vs library**
- Library and version in use.
- Syntax fragments that vary across implementations (e.g., `$..` recursive descent, predicates).

**B6. Search query DSL vs engine**
- DSL flavor and engine version.
- Escaping rules, special characters, query-string vs DSL JSON form.

**B7. ORM vs raw SQL semantic differences**
- ORM library and version.
- Lazy vs eager loading assumptions; transaction boundaries; nullability handling.

## Cross-bucket questions to answer at the end

Q1: Are there any compatibility constraints that span two sub-buckets that single-bucket analysis would miss (e.g., a regex embedded in a SQL query, a CSS selector built from a search-query result)?
Q2: What's the worst engine-incompatibility hazard introduced by this artifact? Cite [file:line / paragraph].
Q3: Where would a future engine/library upgrade most likely break a query or selector in this diff? Name the line(s) most fragile.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket [B1]–[BN], produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 incompatibility bugs across these [N] sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.
