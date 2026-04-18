# Claude Development Assistant

## Code Rules
@~/.claude/docs/CODE_RULES.md

## File-Global Constants

This rule extends the `constants-location` rule defined in CODE_RULES.md.

**file_global_constants_use_count:** A file-global constant is a module-level named constant declared at the top of a file (for example, an `UPPER_SNAKE_CASE` value assigned at module scope). In production code, every file-global constant must be referenced by at least two methods, functions, or class bodies inside that same file. A default parameter value counts as one reference from the enclosing function. When a constant is referenced by exactly one method, move the constant's value to `config/` and import it at module scope with a local alias inside the consuming method (as the Accept example below shows), OR inline the value as a local constant inside the consuming method provided the value does not reintroduce a literal the magic-values rule would flag.

**Test files are exempt.** Test-file detection uses substring match against the full relative path; a file qualifies when any of the following matches: path contains the segment `/tests/`; filename starts with `test_`; filename contains `_test.`; filename contains `.spec.`; filename contains `conftest`.

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

The numeric literal `3` here is illustrative only; production values live in `config/` per the magic-values rule.

```python
from config.timing import MAXIMUM_RETRIES

def fetch_with_retries(url: str) -> str:
    maximum_retries = MAXIMUM_RETRIES
    for each_attempt_index in range(maximum_retries):
        ...
```

Accept (constant kept at file scope when two or more methods reference it):

A reference counts only when the constant is actually consumed — compared, used in a decision, or passed into code that depends on its value — not when a method merely re-exports it. A file-global constant with zero references is dead code; remove it rather than migrate it to a local.

```python
MAXIMUM_RETRIES = 3

def fetch_with_retries(url: str) -> str:
    for each_attempt_index in range(MAXIMUM_RETRIES):
        ...

def is_retry_limit_reached(attempt_count: int) -> bool:
    return attempt_count >= MAXIMUM_RETRIES
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
