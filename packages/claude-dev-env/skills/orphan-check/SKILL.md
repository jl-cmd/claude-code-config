---
name: orphan-check
description: Finds module-level orphans (UPPER_SNAKE constants, private helpers, dataclass singletons) whose only consumer was a function/class being deleted in the current diff. Uses serena MCP find_referencing_symbols to filter references inside the deleted symbol's body, returns survivors with zero remaining consumers. Caller deletes orphans in the same diff to close Category E. Triggers on "/orphan-check", "find orphans after deletion", "post-deletion cleanup", clean-coder Diff Impact Analysis Surface bullet naming a deletion, Self-Audit Loop iteration surfacing Category E.
---

# orphan-check

Find module-level orphans after a deletion. Symbol-aware via serena MCP.

## Gotchas

- Activate the Serena project before any symbol lookup. Run `mcp__serena__check_onboarding_performed`; when it returns false, run `mcp__serena__activate_project` then `mcp__serena__onboarding`. A populated LSP index lets `find_referencing_symbols` resolve every consumer.
- Escalate dynamic-dispatch files (`getattr`, `globals()`, `eval()`) to manual review for load-bearing candidates. The LSP resolves static references.
- Tag candidates referenced only by `tests/` as `test-only-consumer`. The caller decides delete or relocate.
- Tag `__init__.py` re-exports as `indirect` and verify a package caller consumes the re-export before treating the underlying symbol as an orphan.
- Expand the candidate set to every module-level UPPER_SNAKE the deleted symbol referenced, including symbols imported from `config/`.

## When this skill applies

- clean-coder Diff Impact Analysis Surface bullet names a deletion.
- clean-coder Self-Audit Loop surfaces Category E.
- `/orphan-check <file_path> <deleted_symbol_name>` or "orphans after deleting X".

**Refusals — first match wins; respond with the quoted line and stop.**

- No deleted symbol name: `Need a symbol name to scope the orphan check. Re-invoke with /orphan-check <file_path> <deleted_symbol_name>.`
- File path unresolved: `File not found at <file_path>. Re-invoke with an absolute path or a path relative to the project root.`
- Serena inactive: `Serena project not active. Activate with mcp__serena__activate_project then re-invoke.`

## Process

```
[ ] Step 1: Enumerate candidates
[ ] Step 2: Resolve deletion line range
[ ] Step 3: Classify each candidate
[ ] Step 4: Return orphan table
```

### Step 1 — Enumerate candidates

```
mcp__serena__get_symbols_overview(relative_path="<file_path>", depth=0)
```

Capture module-level UPPER_SNAKE, `def _name(...)`, `class _Name(...)`, dataclass singletons. Record `(line, name, kind)`. Kinds: `constant`, `private_function`, `private_class`, `dataclass_singleton`.

### Step 2 — Resolve deletion range

```
mcp__serena__find_symbol(
  name_path_pattern="<deleted_symbol_name>",
  relative_path="<file_path>",
  include_body=true,
)
```

Capture `(deletion_start_line, deletion_end_line)`.

### Step 3 — Classify each candidate

```
mcp__serena__find_referencing_symbols(
  name_path="<symbol_name>",
  relative_path="<file_path>",
)
```

Each reference:

- **In-body** — same file, `deletion_start_line <= line <= deletion_end_line`. Disappears with the deletion.
- **Survivor** — every other reference.
- **Test-only survivor** — surviving refs sit only in `test_*.py`, `*_test.py`, `/tests/`.

| Survivor count | Test-only? | Classification |
|---|---|---|
| 0 | — | `orphan` |
| ≥ 1 | yes | `test-only-consumer` |
| ≥ 1 | no | `surviving` |

### Step 4 — Return orphan table

| Symbol | Kind | File:line | Survivors | Action |
|---|---|---|---|---|
| `PAGINATION_MAXIMUM_PAGES` | constant | `src/core/orchestrator.py:104` | 0 | delete in same diff |
| `_collect_next_page` | private_function | `src/core/orchestrator.py:331` | 0 | delete in same diff |
| `SCAN_PAGE_SETTLE_MIN_DELAY_SECONDS` | constant | `src/config/pipeline_constants.py:109` | 1 (test-only) | move to fixture or delete |

Empty list: `No orphans detected — the <deleted_symbol_name> deletion is self-contained.`

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This skill — invocation, process, output, refusals. |

## Folder map

- `SKILL.md` — single-file skill. Execution delegates to `mcp__serena__*` tools.
