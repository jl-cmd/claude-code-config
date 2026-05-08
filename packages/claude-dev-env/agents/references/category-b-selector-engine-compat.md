# Category B — Selector / query / engine compatibility

**What this category audits:** CSS selectors, SQL queries, regex patterns, JSON-path / XPath, search-DSL queries, CLI / cmdlet syntax — looking for incompatibility with the specific engine, runtime version, or dialect in use.

**Examples of Category B findings:**
- A CSS selector uses a pseudo-class the target browser engine lacks (e.g. `:has()` on Firefox before 121).
- A SQL `WITH ... AS (... )` CTE on a MySQL version older than 8.0.
- A regex lookbehind in POSIX ERE (which has no lookbehind support).
- A PowerShell cmdlet parameter that exists in PS 7+ but not in Windows PowerShell 5.1.
- A Lucene query syntax fragment fed to an Elasticsearch endpoint that disabled query_string.

**Companion reference:** see `source-material-section-types.md`.

---

## Sub-bucket decomposition (Category B)

| ID | Axis name | Concrete checks |
|---|---|---|
| B1 | CSS / DOM selector vs target browser engine | Pseudo-class support; attribute selectors; `:has()`, `:is()`, `:where()` availability across the supported engine matrix. |
| B2 | SQL syntax vs database version | Window functions, CTEs, JSON operators, dialect-specific functions vs the declared minimum DB version. |
| B3 | Regex syntax vs engine flavor | Lookbehind / lookahead support; named groups (`(?P<…>)` vs `(?<…>)`); backreferences; Unicode character classes. |
| B4 | Shell / CLI / cmdlet syntax vs runtime version | PowerShell 5.1 vs 7+; bash 3 vs 5; cmdlet parameters added in later versions; CLI flag deprecations. |
| B5 | JSON path / XPath / structural query vs library | jq vs Python jsonpath-ng vs JavaScript jsonpath syntax; XPath 1.0 vs 2.0/3.0 functions. |
| B6 | Search query DSL vs engine | Lucene / Elasticsearch / Zoekt / OpenSearch syntax; differences in escaping, fuzzy matching, multi-field queries. |
| B7 | ORM vs raw SQL semantic differences | SQLAlchemy `.filter()` vs `.filter_by()`; Django Q expressions vs raw SQL; lazy vs eager evaluation. |

Use 5–10 sub-buckets for any single audit. For an audit that doesn't touch SQL or web frontends, drop B1 / B2 entirely and split B4 across the relevant runtimes.

---

## Reusable sample prompt template (Category B)

````
Audit [REPO/ARTIFACT] [TARGET ID] for **Category B only** (selector / query / engine compatibility). Skip A, C–K. Sub-bucket forced-exhaustion mode: Category B is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch. See source-material-section-types.md for chunking guidance.]

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
````

For a literal worked example using PR #394 inlined verbatim (Python + PowerShell scheduled-task installer), see `category-a-api-contracts.md` — the diff there is the canonical sample artifact. To audit the same PR for Category B specifically, copy that file's `## Diff` block and paste it under `## Source material` above; the relevant Category B sub-buckets for PR #394 are B4 (PowerShell cmdlet version compat — `Get-ScheduledTask`, `New-ScheduledTaskTrigger`, `New-ScheduledTaskAction` are Windows-only and require PS 5.1+) and B3 (the `(Get-Item '{path}')` pattern in the test helper).
