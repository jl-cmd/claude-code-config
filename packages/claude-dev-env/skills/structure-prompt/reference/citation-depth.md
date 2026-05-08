# Add file:line citations on identifier mentions

When a sub-bucket bullet names an identifier (a function, variable, cmdlet, file path) that also lives in the data body, the bullet earns more value with a `file:line` citation appended.

## Detection

A bullet is a citation candidate when all three hold:

- The bullet contains a backtick-wrapped identifier (e.g., `os.walk`, `New-ScheduledTaskTrigger`, `_log_walk_error`)
- The identifier also appears in the data body
- No `file:line` citation already follows the bullet

## Procedure

1. For each citation candidate, search the data body for the identifier.
2. Find the line where the identifier first appears in each file.
3. Append the citation in this format at the end of the bullet, before the period: `(<file>:<line>)`.

## Multiple occurrences

When the identifier appears more than once across the data body:

- 1–3 occurrences → cite all of them: `(file_a.py:42, file_a.py:88, file_b.ps1:12)`
- 4 or more → cite the first and last with `…` between: `(file_a.py:42, …, file_b.ps1:200)`

## Examples

Before:
```
- `os.walk(root, onerror=_log_walk_error, topdown=False)` — `_log_walk_error` matches the exact signature stdlib calls.
```

After (3 occurrences: definition, plus two call sites):
```
- `os.walk(root, onerror=_log_walk_error, topdown=False)` — `_log_walk_error` matches the exact signature stdlib calls (`sweep_empty_dirs.py:23, sweep_empty_dirs.py:33`).
```

Before:
```
- `Get-ScheduledTask`, `New-ScheduledTaskTrigger`, `New-ScheduledTaskAction`, `Register-ScheduledTask`, `Unregister-ScheduledTask` — verify each call's parameter shape.
```

After (one occurrence per cmdlet):
```
- `Get-ScheduledTask` (`Install-SweepEmptyDirs.ps1:248`), `New-ScheduledTaskTrigger` (`Install-SweepEmptyDirs.ps1:297`), `New-ScheduledTaskAction` (`Install-SweepEmptyDirs.ps1:296`), `Register-ScheduledTask` (`Install-SweepEmptyDirs.ps1:300`), `Unregister-ScheduledTask` (`Install-SweepEmptyDirs.ps1:267`) — verify each call's parameter shape.
```

## What stays put

When the identifier is a generic concept (e.g., `if version`, `if FLAG`) rather than a real symbol in the data body, the bullet stays as-written. Citations apply to actual identifiers, not category-shaped placeholders.

When the identifier sits in a file the data body doesn't include (e.g., the bullet mentions `os.walk` but the diff doesn't define it), the citation skips that identifier. Mention this in the report so the user knows the source wasn't available.
