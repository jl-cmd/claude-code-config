# State-File Contract

Downstream stateful skills get richer compaction summaries when their
state file follows the schema below. The contract is intentionally narrow:
six fields, all optional. Populate what makes sense for the skill; omit
the rest.

## Table of contents

1. [Where the file lives](#where-the-file-lives)
2. [Fields the hook recognizes](#fields-the-hook-recognizes)
3. [Worked example: pr-converge](#worked-example-pr-converge)
4. [Worked example: a hypothetical /sweep skill](#worked-example-a-hypothetical-sweep-skill)
5. [Anti-patterns](#anti-patterns)

## Where the file lives

Two storage locations, in scan order:

1. **`$CLAUDE_JOB_DIR/<name>-state.json`** — preferred. The job dir is
   per-invocation, scoped, and naturally cleaned up. Three names are
   pre-registered: `pr-converge-state.json`, `bugteam-state.json`,
   `loop-state.json`. Other names require a one-line registry edit
   ([`registry-extension.md`](registry-extension.md)).
2. **`<cwd>/.claude/state/*.json`** — project-local fallback. Every
   `*.json` file under this directory is scanned in lexicographic order.
   Use this when the skill runs attached to a project checkout and you
   want the state to survive past a single job.

When both locations have a state file, the job-dir file wins (it scans
first).

## Fields the hook recognizes

| Field | Type | What it pins in the directive |
|-------|------|-------------------------------|
| `skill` | string | Identifies which skill is in flight. Lets the compactor LLM disambiguate when the user has several stateful skills installed. |
| `phase` | string | The skill's named phase (e.g. `BUGBOT`, `BUGTEAM`, `COPILOT_WAIT`, `polling`, `awaiting-review`). Survives compaction so the next tick resumes mid-flow. |
| `current_head` | string | The commit SHA the skill currently treats as canonical. The single most load-bearing pointer for any PR-loop skill. |
| `tick_count` | integer | Integer tick number for loop-shaped skills. Renders as `tick_count: <n>`. |
| `worktree` | string | Filesystem path to the worktree the skill is operating inside. Mandatory when the skill enters a worktree on each tick. |
| `operator_followups` | list of strings | Free-form bullets the operator (or the skill) wants surfaced to the next session. Capped at five rendered entries. |

Other fields in the state file are ignored by the hook. They are still
useful for the skill's own state-tracking — the hook does not need to
know about them.

## Worked example: pr-converge

```json
{
  "skill": "pr-converge",
  "phase": "BUGTEAM",
  "current_head": "9c1f7e2a8d4b5c6f3a0e8d2b1c4a7f6e9d3b8c5a",
  "tick_count": 12,
  "worktree": "/repos/claude-code-config/.claude/worktrees/pr-converge-144",
  "operator_followups": [
    "verify bugbot trigger comment was acknowledged at tick 11",
    "copilot review still pending at current_head"
  ],
  "bugbot_clean_at": null,
  "copilot_clean_at": null,
  "bugbot_acknowledged_at": "2026-05-22T14:32:11Z"
}
```

The hook ignores `bugbot_clean_at`, `copilot_clean_at`, and
`bugbot_acknowledged_at` — those are pr-converge's own state. The
directive pins the six recognized fields and tells the compactor to
re-read the state file on resumption to recover the rest.

## Worked example: a hypothetical /sweep skill

```json
{
  "skill": "monitor-open-prs",
  "phase": "audit-loop",
  "tick_count": 4,
  "operator_followups": [
    "PR #381 has bugbot findings unaddressed at current_head"
  ]
}
```

Four fields, no `current_head` or `worktree` because the skill operates
across many PRs and is not anchored to one. The directive renders only
those four lines plus the standard drop-list and resumption hint.

## Anti-patterns

- **Storing entire review bodies inside the state file.** The hook caps
  state-file size at 256 KB and the drop-list explicitly tells the
  compactor to discard per-finding bodies. Store IDs and counts; rebuild
  bodies from GitHub on demand.
- **Putting `current_head` in `operator_followups` as prose.** Use the
  dedicated field. The compactor LLM is more likely to retain a
  structured pointer than a sentence containing a SHA.
- **Setting `phase` to a sentence.** Phases should be short identifiers
  (one or two words, ALL_CAPS or kebab-case). Sentences belong in
  `operator_followups`.
- **Writing the state file at every tool call.** Atomic-write the file
  at tick boundaries (tick start + tick end) — that is when the data
  has actually changed. Compaction can fire at any point, so the
  on-disk state should always reflect the most recent committed tick.
