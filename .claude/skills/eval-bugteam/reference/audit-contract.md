# Audit Contract

Shared between bugteam audit subagents and the lead orchestrator.

## Finding Shape

Each finding in the outcome XML has these fields:

| Field | Type | Required |
|-------|------|----------|
| `finding_id` | `loop<L>-<K>` | yes |
| `severity` | P0/P1/P2 | yes |
| `category` | A-J | yes |
| `file` | path | yes |
| `line` | int | yes |
| `description` | text | yes |
| `recommended_fix_constraint` | text | no |
| `adversarial_pass` | text | yes |
| `gate_output_consistent` | bool | yes |
| `pr_body_cross_ref` | bool | yes |
| `cross_file_pattern` | bool | yes |

## Severity Levels

| Level | Meaning |
|-------|---------|
| P0 | Crash, data loss, security breach |
| P1 | Behavioral regression, incorrect output |
| P2 | Style/compliance, maintainability |

## Categories (A-J)

A = API contracts
B = Selector/query/engine compatibility
C = Resource cleanup
D = Variable scoping
E = Dead code
F = Silent failures
G = Off-by-one/bounds
H = Security
I = Concurrency
J = Magic values/config drift

## Output File Convention

- Raw findings from haiku peers: `loop-<L>-<letter>.outcomes.xml`
- Rejected findings: `loop-<L>-diagnostics.json` under `validator_rejected`
- Merged/validated output: `.bugteam-pr<N>-loop<L>.outcomes.xml`
