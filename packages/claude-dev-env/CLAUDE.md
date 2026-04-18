# Claude Development Assistant

## Code Rules
@~/.claude/docs/CODE_RULES.md

## File-Global Constants

**file_global_constants_use_count:** A file-global constant is a module-level named constant declared at the top of a file (for example, an `UPPER_SNAKE_CASE` value assigned at module scope). In production code, every file-global constant must be referenced by at least two methods or functions inside that same file. When a constant is referenced by exactly one method, declare it as a local constant inside that method instead.

**Test files are exempt.** Test-file detection uses substring match against the full relative path; a file qualifies when any of the following matches: path contains the segment `tests/`; filename starts with `test_`; filename contains `_test.` followed by an extension (e.g. `foo_test.py`); filename contains `.spec.` (e.g. `foo.spec.ts`); filename equals `conftest.py`.

**`config/` files are exempt.** Constants placed in `config/` satisfy the constants-location rule; the use-count requirement applies only to production code outside `config/`.

Flag (single method references the file-global constant — move it inside the method):

```python
MAXIMUM_RETRIES = 3

def fetch_with_retries(url: str) -> str:
    for each_attempt_index in range(MAXIMUM_RETRIES):
        ...
```

Accept (constant declared locally when only one method uses it):

The local form must bind its value to something sourced from config (an import, a function argument, or another already-named constant); it must not reintroduce a numeric or string literal.

```python
from config.timing import MAXIMUM_RETRIES

def fetch_with_retries(url: str) -> str:
    maximum_retries = MAXIMUM_RETRIES
    for each_attempt_index in range(maximum_retries):
        ...
```

Accept (constant kept at file scope when two or more methods reference it):

```python
MAXIMUM_RETRIES = 3

def fetch_with_retries(url: str) -> str:
    for each_attempt_index in range(MAXIMUM_RETRIES):
        ...

def reset_retry_counter() -> int:
    return MAXIMUM_RETRIES
```

## Core Philosophy

**TDD IS NON-NEGOTIABLE.** Build it right, build it simple. Maintainable > Clever.

## Expectations for Claude

1. **ALWAYS FOLLOW TDD** - No production code without failing test
2. **MANDATORY SELF-CHECK before proposing** - See protocol below
3. Assess refactoring after every green

**BEFORE proposing plans/implementation:**

☐ "Is this KISS?" (simplest? unnecessary complexity?)
☐ "Over-engineering?" (multiple files? premature abstractions?)
☐ Test infrastructure? (ONE file, functions, YAGNI)
☐ Tests add value? (no existence checks, no constant tests)
☐ Files (proper modules, correct dirs, no empty __init__.py)
☐ Quality (DRY, types complete, no Any/any)

## Additional Non-overlapping Rules

- **task_scope:** Match every action to what was explicitly requested. When intent is ambiguous, research official docs and present options via AskUserQuestion before making any changes. Proceed with edits only on explicit instruction.

## Tool Policies
- **context7:** Before writing code using any library/framework/SDK/API, call `resolve-library-id` then `query-docs` via Context7 MCP. Use the fetched docs to write code. Applies to all libs including React, Next.js, Django, Express, Prisma.

## Compaction
When compacting, always preserve:
- Active task and current goal
- Full list of modified files
- Any failing test names or error messages
- Current git branch and PR state
