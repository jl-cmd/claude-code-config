# Audit Contract

Shared contract between bugteam audit subagents and the pr-converge
orchestrator for outcome shape, validation rules, and diagnostic signaling.

## Finding XML Schema

Each `<finding>` element in a bugteam outcome XML carries these attributes:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `finding_id` | string | yes | `loop<L>-<K>` — scoped to the audit loop |
| `severity` | enum | yes | `P0` = crash, `P1` = behavioral regression, `P2` = style/compliance |
| `category` | letter | yes | `A`–`J` per bugteam audit rubric |
| `file` | path | yes | Relative path from repo root |
| `line` | int | yes | Line number the finding targets |
| `finding_comment_id` | int | no | GitHub child comment ID after review POST |
| `finding_comment_url` | string | no | URL of the child comment or fallback |
| `used_fallback` | bool | yes | `true` when review POST failed and fallback was used |
| `gate_output_consistent` | bool | yes | `true` when the finding does not contradict gate output |
| `pr_body_cross_ref` | bool | yes | `true` when the finding was cross-referenced against the PR body |
| `cross_file_pattern` | bool | yes | `true` when the finding identifies a cross-file pattern |

## Verified-Clean Entry

Each `<verified_clean>` entry requires:

- `letter` — category letter
- `name` — category name
- `evidence` — one complete execution path traced from entry to exit,
  naming the function and the path. Surface-level scanning is
  insufficient.

## Validator Rejection Schema

When the opus validator rejects a haiku peer's finding, it writes a
JSON entry to `loop-<L>-diagnostics.json` under `validator_rejected`:

```json
{
  "source_file": "loop-<L>-<letter>.outcomes.xml",
  "rejection_reason": "file_not_found|line_out_of_bounds|excerpt_mismatch|category_invalid|severity_invalid|duplicate",
  "original_finding_id": "loop<L>-<K>",
  "details": "human-readable explanation"
}
```

## Diagnostics JSON Required Keys

Each `loop-<L>-diagnostics.json` file must include:

- `validator_rejected` — array of rejected findings (see schema above)
- `haiku_count` — number of haiku XMLs consumed
- `haiku_timeout_count` — number of haiku slots that timed out
- `validator_started_at` — ISO-8601 timestamp
- `validator_completed_at` — ISO-8601 timestamp
- `total_after_dedup` — final finding count after validation + dedup
