# Future Extensions

Out-of-scope for v1. Tracked here so the v1 surface stays minimal and
the ideas are recoverable when real demand surfaces.

## Headless-Claude-in-hook synthesis

The v1 hook is pure templating: it renders fields it knows about and
emits a fixed drop-list. A future v2 could spawn a headless Claude
process from inside the hook to generate a state-file-specific drop list
("on this pr-converge state with `phase: COPILOT_WAIT` and zero unresolved
threads, the compactor can drop the BUGBOT trigger history entirely").

Reasons this is deferred:

- The PreCompact event has a wall-clock budget (10 s default timeout in
  `hooks.json`). Spawning headless Claude blows through that budget on
  most invocations.
- The compactor LLM already does the synthesis work. The hook would be
  shadowing the compactor's job for marginal gain.
- Real-world usage data on the v1 templating approach should land first
  to identify which state-file shapes need synthesized guidance.

## Multi-state directive aggregation

The v1 hook returns the FIRST matching state file and stops. A future
version could aggregate every matching state file into one directive
(MUST PRESERVE block listing all of them, one drop-list, one resumption
hint per path).

Reasons this is deferred:

- Stateful skills generally do not run concurrently in the same job dir.
- Aggregation increases the directive's token count without obvious
  benefit when only one skill is actually active.
- First-match-wins is easier to reason about and easier to test.

## Transcript-aware filtering

The hook could read the transcript file (`transcript_path` is in the
stdin payload) to identify which tool calls dominated context and add
those categories to the drop list dynamically. For example, if the
transcript shows 50 `gh api repos/.../pulls/N/reviews` calls, the drop
list could explicitly call out "GitHub review-list pagination payloads."

Reasons this is deferred:

- Reading the transcript inside the hook risks timeout on large
  transcripts.
- The v1 drop list already covers the chaff categories that show up
  in pr-converge / bugteam / loop transcripts.
- Static drop lists are easier to audit than dynamically-generated ones.

## PostCompact verification

A companion `PostCompact` hook could read the post-compaction summary
and emit a warning when load-bearing pointers (the state-file path,
`current_head`) are missing. This would be a feedback signal to tune
the directive over time.

Reasons this is deferred:

- The post-compaction summary is not directly exposed to hooks; reading
  it requires re-reading the transcript after compaction.
- The cost of a missed pointer is high but recoverable (re-read the
  state file manually). The cost of a noisy warning hook is low but
  cumulative.
- A manual spot-check process is sufficient for early validation.

## Configurable drop-list

Right now the drop list is a tuple of six strings in the constants
module. A future version could expose a `<skill-name>.dropfile` mechanism
where skills register their own additional drop-list entries (e.g.
bugteam contributes "audit-rubric category prompts loaded into context").

Reasons this is deferred:

- Six categories cover the cross-cutting chaff well.
- Per-skill drop lists multiply maintenance surface area.
- Skills that need bespoke guidance can populate `operator_followups`
  with a one-liner like "compactor: drop audit-rubric category prompts."
