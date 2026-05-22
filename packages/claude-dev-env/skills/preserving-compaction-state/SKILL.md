---
name: preserving-compaction-state
description: >-
  Ships a PreCompact hook that detects an in-flight stateful skill
  (pr-converge, bugteam, /loop, /monitor-open-prs, and any sibling skill
  whose state file lives at $CLAUDE_JOB_DIR/<name>-state.json or
  <project>/.claude/state/*.json), then prints a focus directive that
  Claude Code appends to the compactor's custom_instructions. The directive
  pins the state-file path, current_head SHA, worktree, phase, and operator
  follow-ups, and lists the verbose chaff (per-finding bodies, stale SHAs,
  thread IDs, per-tick narrations) that the summary should drop. Use when
  the user says '/preserving-compaction-state', 'preserve skill state across
  compaction', 'add a precompact hook', 'survive auto-compaction', 'protect
  pr-converge state from /compact', or asks how stateful skills retain their
  pointers across context boundaries.
---

# Preserving Compaction State

A `PreCompact` hook that turns "rich state file on disk" into "high-signal
compaction summary." The hook is templating-only — it does not synthesize
prose. The compactor LLM writes the actual summary. The hook only injects
structured guidance that scales with how richly the skill's state file is
populated.

The value of this skill compounds the more diligently downstream stateful
skills follow the [state-file contract](reference/state-file-contract.md).

## Gotchas

Highest-signal content. Append a bullet each time the hook fails to
preserve a load-bearing pointer that the next session needed.

- **PreCompact stdout becomes custom compact instructions, not user-visible
  prose.** On exit 0, Claude Code appends hook stdout to the compactor LLM's
  `custom_instructions`. The operator never sees the directive directly;
  only the next session's summary reflects it. Test by checking the next
  session's recall of pinned fields, not by reading the transcript.
- **Exit code 2 BLOCKS compaction.** This skill never returns 2. Always 0,
  even on a corrupt state file. A failed read is a no-op (zero stdout),
  not a blocked compaction.
- **No `hookSpecificOutput.additionalContext` for PreCompact.** The event
  does not support context injection via the structured JSON output channel
  used by `SessionStart` and `UserPromptSubmit`. Stdout text IS the only
  injection path. Sending `{"hookSpecificOutput": {...}}` is ignored.
- **`$CLAUDE_JOB_DIR` is the dominant registry root.** Project-local
  `.claude/state/*.json` is a fallback. When a job runs detached from a
  project (background, scheduled), only the job dir is populated and the
  project scan finds nothing — this is expected.
- **State-file size cap is intentional.** Files larger than 256 KB are
  skipped to bound the hook's own footprint. A state file growing past
  256 KB contains chaff the skill author should prune, not chaff the hook
  should accommodate.
- **`trigger: "manual"` echoes operator `custom_instructions` first.** When
  the user typed something at the `/compact` prompt, that text leads the
  hook's output, the templated directive follows. The operator's intent
  always appears above the hook's directive.

## When this skill applies

The skill activates automatically on every `/compact` invocation and every
auto-compaction event in any plugin that ships these hooks. There is no
slash command to invoke it by hand. Mention the skill name in chat when:

- Authoring a new stateful skill that needs its pointers to survive
  compaction → read the [state-file contract](reference/state-file-contract.md).
- Adding a new state-file location to the hook's scan registry → read
  [registry extension](reference/registry-extension.md).
- Debugging why a pointer disappeared from a post-compaction session →
  read [output format](reference/output-format.md) and inspect the hook's
  stdout against a synthetic payload.

**Refusal cases — first match wins:**

- **PreCompact event payload missing.** The hook is invoked by the
  Claude Code harness; it has no manual invocation surface. If the user
  asks to "run the hook," respond exactly: `precompact_state_preserver
  has no manual invocation — it fires on /compact and auto-compaction.`

## How the hook works

The script lives at `packages/claude-dev-env/hooks/lifecycle/precompact_state_preserver.py`
alongside the other lifecycle hooks. Constants are split into
`packages/claude-dev-env/hooks/hooks_constants/precompact_state_preserver_constants.py`
per house convention. The test suite is the sibling
`packages/claude-dev-env/hooks/lifecycle/test_precompact_state_preserver.py`
(seven round-trip tests covering match, no-match, manual trigger echo,
malformed stdin, project-local fallback, size cap, wrong event name).

The flow per fire:

1. Read PreCompact JSON payload from stdin (`session_id`, `transcript_path`,
   `cwd`, `permission_mode`, `hook_event_name`, `trigger`,
   `custom_instructions`).
2. Skip silently when `hook_event_name != "PreCompact"`.
3. Enumerate candidate state-file paths in deterministic order:
   `$CLAUDE_JOB_DIR/pr-converge-state.json`,
   `$CLAUDE_JOB_DIR/bugteam-state.json`,
   `$CLAUDE_JOB_DIR/loop-state.json`,
   then every `*.json` under `<cwd>/.claude/state/`.
4. Load the first candidate that exists, parses as a JSON object, and is
   under the 256 KB cap.
5. When `trigger == "manual"` and `custom_instructions` is non-empty,
   echo the operator's text first.
6. Render the focus directive — MUST PRESERVE block (state-file path,
   `skill`, `phase`, `current_head`, `tick_count`, `worktree`,
   `operator_followups`), CAN DROP block (verbose chaff catalog),
   RESUMPTION HINT (re-read the state file on resumption).
7. Print to stdout, exit 0.

## State-file contract for downstream skills

Stateful skills get richer compaction summaries when they populate the
fields the hook knows how to pin. Full contract:
[`reference/state-file-contract.md`](reference/state-file-contract.md).
Minimum payload that benefits:

```json
{
  "skill": "pr-converge",
  "phase": "BUGTEAM",
  "current_head": "abc123def456",
  "tick_count": 7,
  "worktree": "/work/pr-converge-144",
  "operator_followups": ["confirm bugbot acknowledged trigger comment"]
}
```

Any subset works. Missing fields are silently omitted from the directive
(no placeholders, no `null`-rendering).

## Adding a new skill to the registry

The hook scans `$CLAUDE_JOB_DIR/<name>-state.json` for three known names
out of the box (`pr-converge`, `bugteam`, `loop`) and any `*.json` under
`<cwd>/.claude/state/`. Adding a fourth dedicated job-dir filename is a
one-line edit. See [`reference/registry-extension.md`](reference/registry-extension.md).

## Hook registration

Wired in `packages/claude-dev-env/hooks/hooks.json`:

```json
"PreCompact": [
  {
    "matcher": "manual|auto",
    "hooks": [
      {
        "type": "command",
        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/lifecycle/precompact_state_preserver.py",
        "timeout": 10
      }
    ]
  }
]
```

For users who consume the plugin and want to disable the hook in their
own `settings.local.json`, remove the entry; the rest of the plugin is
unaffected. The hook is advisory (exit 0 always), so leaving it enabled
on a system with no stateful skills active is also a no-op.

## File index

| File | Purpose |
|------|---------|
| [`SKILL.md`](SKILL.md) | This hub — what the skill does, contract, gotchas, registration |
| [`reference/state-file-contract.md`](reference/state-file-contract.md) | Field-by-field schema downstream skills should populate |
| [`reference/registry-extension.md`](reference/registry-extension.md) | How to add a new state-file location to the scan registry |
| [`reference/output-format.md`](reference/output-format.md) | The exact directive template, with annotated example |
| [`reference/future-extensions.md`](reference/future-extensions.md) | Deliberately out-of-scope ideas tracked for later |
| [`reference/sources.md`](reference/sources.md) | Citations: PreCompact spec, Anthropic context-engineering posts |

## Folder map

- `SKILL.md` — hub.
- `reference/` — schema, registry, output template, citations, future work.

The hook script and its tests live under
`packages/claude-dev-env/hooks/lifecycle/` (canonical lifecycle-hook
location); constants live under
`packages/claude-dev-env/hooks/hooks_constants/`.
