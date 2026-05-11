---
name: bounds-check
description: Audits bounded loops in a file or directory for silent cap exits and cap-name semantic drift. Locates `for X in range(CAP):`, `while count < CAP:`, and `itertools.islice` patterns via serena MCP search_for_pattern; reads the loop body to confirm a cap-reached log emits when the cap fires; inspects the cap constant's name against its semantic (per-page vs total work). Returns the list of bounded loops missing cap-reached logs or carrying semantically drifted names so the caller adds the log or renames in the same diff to close Category G (Bounds / silent cap exits / time-zone footguns). Triggers on "/bounds-check", "audit bounded loops", "find silent cap exits", any clean-coder Diff Impact Analysis Bounds bullet listing a new cap, Self-Audit Loop iteration surfacing Category G.
---

# bounds-check

Audit bounded loops for silent cap exits and name semantic drift. Backed by serena.

## Gotchas

- Match three loop shapes per file: `for X in range(<CAP>):`, `while <counter> < <CAP>:`, and `itertools.islice(<iterable>, <CAP>)`. Each shape carries a distinct regex.
- Treat `while True:` plus an inner `if <counter> > <CAP>: break` as a bounded loop. Tag the cap location at the `break` line.
- Audit cap-reached signalling at three sites: a log call inside the final iteration, a log call after the loop block, or a return-with-warning structure. Tag the loop `signalled` when any site fires on the cap path; tag `silent` when every cap exit lacks a signal.
- Inspect the cap constant's name semantic: a name shaped `MAXIMUM_X_PER_BATCH` bounds a single API call's page size; a name shaped `MAXIMUM_X_TOTAL` bounds total work. Tag `name-drift` when the constant flows into a per-call API parameter under a name shaped for a total cap (the PR-108 `MAXIMUM_DISCOUNT_EMAILS_PER_BATCH` case).
- Audit wall-clock and timezone reads colocated with the bounded loop in the same pass. `date.today()` or `datetime.now()` sampled inside the loop body produces UTC-midnight straddle drift; tag `wall-clock-per-iter` so the caller hoists the sample.

## When this skill applies

- clean-coder Diff Impact Analysis Bounds bullet lists a new cap, page size, loop limit, or wall-clock read.
- clean-coder Self-Audit Loop surfaces Category G (G3 cap-exit silence, G6 name drift, I2 wall-clock straddle).
- `/bounds-check <file_path>` or `/bounds-check <directory_path>`.

**Refusals — first match wins; respond with the quoted line and stop.**

- File or directory path unresolved: `Path not found at <input_path>. Re-invoke with an absolute path or a path relative to the project root.`
- Serena project inactive: `Serena project not active. Activate with mcp__serena__activate_project then re-invoke.`

## Process

```
[ ] Step 1: Locate bounded loops
[ ] Step 2: Resolve each loop's cap constant
[ ] Step 3: Inspect cap-reached signalling and wall-clock reads
[ ] Step 4: Return the bounds table
```

### Step 1 — Locate bounded loops

Run three pattern searches, each scoped to the input path:

```
mcp__serena__search_for_pattern(
  substring_pattern="for\\s+\\w+\\s+in\\s+range\\(",
  relative_path="<input_path>",
  context_lines_after=10,
)

mcp__serena__search_for_pattern(
  substring_pattern="while\\s+\\w+\\s*<\\s*\\w+\\s*:",
  relative_path="<input_path>",
  context_lines_after=10,
)

mcp__serena__search_for_pattern(
  substring_pattern="itertools\\.islice\\(",
  relative_path="<input_path>",
  context_lines_after=10,
)
```

Capture each match as `(file, loop_start_line, loop_shape)`. Shapes: `range`, `while-counter`, `islice`.

### Step 2 — Resolve each loop's cap constant

For every match, extract the cap argument from the captured line:

- `range(<CAP>)` → `<CAP>` is the cap.
- `while <counter> < <CAP>:` → `<CAP>` is the cap.
- `itertools.islice(<iter>, <CAP>)` → second positional arg is the cap.

When `<CAP>` is an UPPER_SNAKE identifier, look up its definition via `mcp__serena__find_symbol` and capture the assigned value plus the file path. When `<CAP>` is a literal, record the literal.

### Step 3 — Inspect cap-reached signalling and wall-clock reads

Read the loop body (the lines captured in Step 1's `context_lines_after=10`). Tag each loop:

- **`signalled`** — body or trailing block calls `log_warning`, `log_error`, `raise`, or returns a result type whose name carries `cap`, `limit`, `reached`, or `truncated`.
- **`silent`** — no signal of the kind above on the cap path.
- **`name-drift`** — the cap constant's name carries `MAXIMUM_*_TOTAL` semantics, and the cap flows into a per-call API parameter (Gmail `maxResults`, Sheets `pageSize`, HTTP query `?per_page=`). Resolve the call chain via serena `find_referencing_symbols` on the cap constant.
- **`wall-clock-per-iter`** — the loop body calls `date.today()`, `datetime.now()`, `time.time()`, or a function whose name carries `today`, `now`, or `_today_in_*`.

A single loop can carry multiple tags.

### Step 4 — Return the bounds table

| File:line | Loop shape | Cap constant | Tags | Action |
|---|---|---|---|---|
| `src/core/orchestrator.py:208` | range | `PAGINATION_MAXIMUM_PAGES = 50` | silent | add `log_warning("page cap reached: %d", PAGINATION_MAXIMUM_PAGES)` on the cap path |
| `src/config/pipeline_constants.py:121` | range | `MAXIMUM_DISCOUNT_EMAILS_PER_BATCH = 500` | name-drift | rename to `DISCOUNT_GMAIL_PAGE_SIZE` to match the per-call `maxResults` semantic |
| `src/services/gmail_discount_scanner.py:108` | range | `len(messages)` | wall-clock-per-iter | sample `_today_in_utc()` once before the loop and pass as parameter |
| `shared_utils/gmail/gmail_service.py:227` | while-counter | `True` | silent | add a `MAXIMUM_PAGINATION_PAGES` cap and a cap-reached log |

Append a coverage line: total loops, signalled, silent, name-drift, wall-clock-per-iter.

Empty result: `No bounded loops found at <input_path>.`

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This skill — invocation, process, output, refusals. |

## Folder map

- `SKILL.md` — single-file skill. Execution delegates to `mcp__serena__*` tools.
