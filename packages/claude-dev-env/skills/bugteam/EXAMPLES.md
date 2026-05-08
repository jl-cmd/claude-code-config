# Examples

Concrete exit scenarios for bugteam. The process [`SKILL.md`](SKILL.md) defines the flow; this file shows what each terminal state looks like in practice.

## Exit scenarios

### `converged` — clean audit, no fix needed

Loop 1 audit returns zero findings. Fix step skipped. Cycle exits.

```
/bugteam exit: converged
Loops: 1
Starting commit: abc1234
Final commit: abc1234
Net change: 3 files, +15/-2

Loop log:
1 audit: 0P0 0P1 0P2
```

### `converged` — fix resolved all findings

Loop 1 audit finds bugs. Fix step resolves all of them. Loop 2 audit returns zero findings. Cycle exits.

```
/bugteam exit: converged
Loops: 2
Starting commit: abc1234
Final commit: def5678
Net change: 3 files, +15/-2

Loop log:
1 audit: 1P0 2P1 0P2 → fix: fixed all 3
2 audit: 0P0 0P1 0P2
```

### `cap reached` — fix made progress but didn't converge in 10 loops

Bugteam ran 10 full audit-fix cycles on a multi-file PR. The first 8 were productive; loops 9 and 10 each found 2 new P2 issues. The lead acknowledges the progress and suggests follow-up with `/findbugs`.

```
/bugteam exit: cap reached
Loops: 10
Starting commit: abc1234
Final commit: hij9012
Net change: 7 files, +45/-12

Loop log:
1 audit: 3P0 2P1 0P2 → fix: fixed all 5
2 audit: 0P0 1P1 2P2 → fix: fixed 2 of 3
3 audit: 0P0 1P1 1P2 → fix: fixed 1 of 2
4 audit: 0P0 1P1 0P2 → fix: fixed 1 of 1
5 audit: 0P0 0P1 1P2 → fix: fixed 1 of 1
6 audit: 0P0 0P1 0P2 → fix: (no fix needed)
7 audit: 0P0 0P1 0P2 → fix: (no fix needed)
8 audit: 0P0 0P1 0P2 → fix: (no fix needed)
9 audit: 0P0 0P1 0P2 → fix: (no fix needed)
10 audit: 0P0 0P1 0P2 → fix: (no fix needed)
```

### `stuck` — fix subagent made zero progress

Loop 1 audit found bugs. Fix step committed nothing (hook-blocked or could_not_address all findings). Same HEAD. Cycle exits.

```
/bugteam exit: stuck
Loops: 1
Starting commit: abc1234
Final commit: abc1234
Net change: 3 files, +15/-2

Loop log:
1 audit: 1P0 2P1 0P2 → fix: stuck (0 of 3 addressed)
```

### `error` — pre-flight or tool failure

```
/bugteam exit: error
Loops: 0
Starting commit: abc1234
Final commit: abc1234
Net change: (tool failed before diff capture)

Error: Required subagent type 'clean-coder' not installed.
```

## Additional examples

### When findings are fixed, replies are posted inline

After the fix commit, each finding gets a reply:

```
Fixed in def5678. → (thread resolves)
Could not address this loop: file is generated, cannot edit. → (thread stays open)
```

### When a finding cannot be addressed, the reason is carried forward

The bugfix teammate writes one outcome per finding to `.bugteam-loop-2.fix-outcomes.xml`. Findings with `status=could_not_address` carry their `<reason>` text, and the teammate posts a matching reply to each finding comment so the reviewer sees why each bug stayed open.

### When all findings are fixed, the review uses "→ clean" suffix

The review body's total line appends `→ clean` when zero findings remain, enabling the re-invocation scan to short-circuit. See Loop 2 in the `converged` example above.
