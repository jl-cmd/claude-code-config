# Surface cleanup

The optimized prompt has consistent surface formatting.

## Pass list

| Surface | State after cleanup |
|---|---|
| Typos in mission, metadata, framework, output spec, or questions | Spelled correctly |
| Bullet style within a single section | Single style throughout (`-`) |
| Code block language tags | Every fenced block carries a language tag |
| Trailing whitespace on lines | Removed |
| Runs of 3+ blank lines | Collapsed to one blank line |
| Heading levels | Sequential within each block (no jumps from `#` to `###`) |

## Scope

This pass changes surface formatting only. Identifiers, content, and ordering pass through unchanged.
