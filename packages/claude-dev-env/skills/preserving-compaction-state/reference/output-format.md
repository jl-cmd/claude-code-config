# Output Format

The exact text the hook prints to stdout when a state file is found.

## Table of contents

1. [Template](#template)
2. [Annotated example](#annotated-example)
3. [Manual trigger with operator instructions](#manual-trigger-with-operator-instructions)
4. [Why this shape](#why-this-shape)

## Template

```
[precompact-state-preserver] A stateful skill is in flight. Preserve the load-bearing pointers below and drop the verbose chaff.

MUST PRESERVE (load-bearing pointers):
- state_file_path: <absolute posix path to the matched state file>
- skill: <value from state file>
- phase: <value from state file>
- current_head: <value from state file>
- tick_count: <value from state file>
- worktree: <value from state file>
- operator_followups:
    - <first followup item>
    - <second followup item, up to five>

CAN DROP (verbose chaff that re-derives from pointers):
- Per-finding bodies from bugbot/bugteam/copilot reviews — keep counts and IDs only.
- Intermediate commit SHAs that are not current_head and are not clean-at markers.
- GitHub thread IDs, review IDs, and comment IDs already resolved or replied to.
- Per-tick narration prose ("on tick N I did X, then Y") — keep the latest phase only.
- Raw tool-call outputs and JSON payloads already summarized into state fields.
- Repeated reproductions of file contents Claude can re-read from current_head.

RESUMPTION HINT:
Re-read <state_file_path> on resumption to recover full skill state.
```

Fields that are missing or empty in the state file are silently omitted
from the MUST PRESERVE block — the directive never renders `null` or
placeholder text. The drop list and resumption hint always render.

## Annotated example

Input state file at `/tmp/job/pr-converge-state.json`:

```json
{
  "skill": "pr-converge",
  "phase": "BUGTEAM",
  "current_head": "abc123",
  "tick_count": 7,
  "worktree": "/work/pr-144",
  "operator_followups": ["confirm bugbot ack at tick 6"]
}
```

PreCompact stdin payload (truncated):

```json
{
  "hook_event_name": "PreCompact",
  "trigger": "auto",
  "cwd": "/tmp",
  "custom_instructions": ""
}
```

Hook stdout (verbatim):

```
[precompact-state-preserver] A stateful skill is in flight. Preserve the load-bearing pointers below and drop the verbose chaff.

MUST PRESERVE (load-bearing pointers):
- state_file_path: /tmp/job/pr-converge-state.json
- skill: pr-converge
- phase: BUGTEAM
- current_head: abc123
- tick_count: 7
- worktree: /work/pr-144
- operator_followups:
    - confirm bugbot ack at tick 6

CAN DROP (verbose chaff that re-derives from pointers):
- Per-finding bodies from bugbot/bugteam/copilot reviews — keep counts and IDs only.
- Intermediate commit SHAs that are not current_head and are not clean-at markers.
- GitHub thread IDs, review IDs, and comment IDs already resolved or replied to.
- Per-tick narration prose ("on tick N I did X, then Y") — keep the latest phase only.
- Raw tool-call outputs and JSON payloads already summarized into state fields.
- Repeated reproductions of file contents Claude can re-read from current_head.

RESUMPTION HINT:
Re-read /tmp/job/pr-converge-state.json on resumption to recover full skill state.
```

## Manual trigger with operator instructions

When `trigger == "manual"` and `custom_instructions` is non-empty, the
operator's text is echoed first, separated by a blank line, then the
templated directive follows. Example with operator instructions
`"keep the deployment approval thread visible"`:

```
keep the deployment approval thread visible

[precompact-state-preserver] A stateful skill is in flight. ...
<rest of the templated directive>
```

The operator's intent always leads. The hook's directive is supplemental.

## Why this shape

Three explicit blocks (MUST PRESERVE, CAN DROP, RESUMPTION HINT) anchor
the compactor LLM around three concrete behaviors. From the Anthropic
context-engineering literature (cited in
[`sources.md`](sources.md)):

- Quantitative pointers with labels survive compaction; bare values
  dropped into prose often do not. Each pointer renders as
  `field_name: value` so the field name itself becomes part of the
  summary's vocabulary.
- An explicit drop list reduces ambiguity. The compactor LLM is more
  likely to discard "per-finding bodies" if the prompt names that
  category outright.
- The resumption hint shifts the burden from the summary to the next
  session: rather than summarizing every state field, the next session
  re-reads the file. The summary just has to remember the file exists
  and where it lives.

Total directive size: roughly 250–400 tokens depending on how many
optional fields the state file populates and how many followups it
carries. Well under the 500-token budget the operator brief calls out.
