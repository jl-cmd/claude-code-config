# Code Rules Gate

Script: `scripts/code_rules_gate.py`

## What It Checks

Runs CODE_RULES.md enforcer against files touched between `--base` and
HEAD. Checks seven violation classes:

1. No new inline comments in production code
2. Imports at top of file (no function-body imports)
3. Logging uses format args (no f-strings in log calls)
4. No magic values in production function bodies
5. Constants in `config/` directory
6. Complete type hints on all parameters and returns
7. No hardcoded user paths

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Pass — no new violations (pre-existing advisories are reported to stderr) |
| 1 | Advisory-only — pre-existing violations in touched files (non-blocking) |
| 2 | New violation — a diff-introduced violation exists (blocking) |

## Usage

```bash
python scripts/code_rules_gate.py --base origin/main
```

The `--base` flag sets the merge-base against which diff lines are
measured. All affected files between `--base` and `HEAD` are checked.

## Integration

eval-bugteam runs this as the pre-audit gate (Step 3.2). If exit code is
non-zero (new violations), the gate blocks the audit — the lead spawns an
eval-clean-coder to fix violations before proceeding.

The gate output is also captured to a `.gate.txt` file and passed to
AUDIT subagents so they can cross-reference hook-related claims against
actual gate output. This prevents false-positive audits that predict
enforcer behavior the gate does not exhibit.
