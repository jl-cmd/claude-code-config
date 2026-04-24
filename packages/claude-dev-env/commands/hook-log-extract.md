---
description: Extract hook-firing records from session transcripts into Neon and show blocker summary
allowed-tools: Bash
---

Scan every JSONL session transcript under
`C:/Users/jon/.claude/projects/`, extract every `attachment` record whose
inner type starts with `hook_`, and load one row per firing into the Neon
`hook_events` table. The Stop hook runs this on every session end using
the `--incremental` flag.

## Run modes

```
bws run -- python packages/claude-dev-env/hooks/diagnostic/hook_log_extractor.py
```

Full extraction using the current byte offsets in
`C:/Users/jon/.claude/logs/hooks/.state/offsets.json`. Equivalent to the
Stop hook's `--incremental` invocation.

```
bws run -- python packages/claude-dev-env/hooks/diagnostic/hook_log_extractor.py --full-rebuild
```

Clear offsets, truncate `hook_events`, and re-read every JSONL from byte
zero. Use this after a schema migration or when the offsets file is
suspected of drift.

```
bws run -- python packages/claude-dev-env/hooks/diagnostic/hook_log_extractor.py --summary
```

Skip extraction. Print the top-10 blockers of the last 24 hours with
their block count and a single truncated command preview, or
`No new blocks since last run.` when the window is empty.

```
bws run -- python packages/claude-dev-env/hooks/diagnostic/hook_log_extractor.py --query <name>
```

Run the pre-baked query `queries/<name>.sql` and print the result as an
aligned text table. Available query names match the SQL files in
`packages/claude-dev-env/hooks/diagnostic/queries/`:

- `top_blockers_overall`
- `top_blockers_since_last_run`
- `blocks_last_7_days`
- `blocks_by_category`
- `blocks_by_tool`
- `block_details_for_hook`

## Offline behavior

If the psycopg connection fails with `OperationalError` or the
5-second timeout elapses, the extractor appends one ISO-8601 line to
`C:/Users/jon/.claude/logs/hook-extractor.log` and exits with status 0.
Session shutdown stays fast, and the next online run backfills from
the existing offsets.
