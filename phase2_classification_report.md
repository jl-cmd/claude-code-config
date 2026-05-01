# Phase 2 Classification Report — `code_rules_other` Relabel

**Date:** 2026-05-01
**Source report:** `gate_audit_report.json` (353 findings, 80 PRs, 19 repos)
**Output report:** `gate_audit_report_relabeled.json`

## Result

`code_rules_other` count dropped from **61 → 0**. Every residual catch-all finding mapped to an existing enforcer rule. No new enforcer rules were needed; this was purely a `run_gate_audit.py`-style mapping-table extension applied as a post-hoc relabel pass against the report JSON.

## Cluster verdicts

The Phase 2 plan predicted 7 clusters from a hand-classification of the 61 catch-all excerpts. The relabel pass against the real report confirmed each prediction within ±0.

| Cluster keyword | Predicted | Actual | Mapped to |
|---|---|---|---|
| `Constant <NAME> - move to config/` | 36 | 36 | `constants_location` |
| `Banned identifier 'response/result/value'` | 11 | 11 | `banned_identifier` |
| `Unjustified # type: ignore` | 8 | 8 | `unjustified_type_ignore` |
| `parameter/function ... missing type annotation` | 2 | 2 | `complete_type_hints` |
| `inline list/set literal ... extract to config/` | 2 | 2 | `magic_values` |
| `tests must cover behavior` | 1 | 1 | `tdd_no_paired_test` |
| `constant-value test - delete` | 1 | 1 | `useless_test` |
| **Total** | **61** | **61** | — |

## Rule counts: before vs after

| Rule | Before | After | Δ |
|---|---|---|---|
| `naming_collections` | 123 | 123 | 0 |
| `magic_values` | 62 | 64 | +2 |
| `constants_location` | 12 | 48 | +36 |
| `naming_loop_variables` | 19 | 19 | 0 |
| `imports_at_top` | 15 | 15 | 0 |
| `unused_optional_parameter` | 12 | 12 | 0 |
| `no_bare_print` | 11 | 11 | 0 |
| `naming_booleans` | 10 | 10 | 0 |
| `tdd_no_paired_test` | 9 | 10 | +1 |
| `windows_rmtree_unsafe` | 8 | 8 | 0 |
| `complete_type_hints` | 6 | 8 | +2 |
| `no_new_inline_comments` | 3 | 3 | 0 |
| `gh_body_arg` | 2 | 2 | 0 |
| `unjustified_type_ignore` | 0 | 8 | **+8 (new)** |
| `banned_identifier` | 0 | 11 | **+11 (new)** |
| `useless_test` | 0 | 1 | **+1 (new)** |
| `code_rules_other` | 61 | **0** | **−61** |
| **Total** | **353** | **353** | 0 |

The total finding count is unchanged (the relabel pass only renames buckets, never adds or drops findings).

## Top 5 leaking rules (after relabel)

| Rule | Count |
|---|---|
| `naming_collections` | 123 |
| `magic_values` | 64 |
| `constants_location` | 48 |
| `naming_loop_variables` | 19 |
| `imports_at_top` | 15 |

`code_rules_other` no longer appears in the top 5; `constants_location` takes its slot at rank 3.

## Residual `code_rules_other` findings

**None.** Every catch-all excerpt matched a keyword in the mapping table. The relabel pass is complete; no items require human triage.

## Implementation

- **Mapping table:** `config/gate_audit_relabel_constants.py` — 14 keyword→rule entries, three of them new labels (`unjustified_type_ignore`, `banned_identifier`, `useless_test`).
- **Relabel pass:** `relabel_gate_audit.py` — reads `gate_audit_report.json`, rebuckets `code_rules_other` findings, recomputes `gate_leaks_by_rule` and `summary.top_leaking_rules`, writes `gate_audit_report_relabeled.json`.
- **Tests:** `test_relabel_gate_audit.py` — 15 cases, all green. Includes an integration test against the real audit report that asserts `code_rules_other ≤ 5` post-relabel.
- **Enforcer changes:** none. Phase 2 confirmed the cluster analysis: every catch-all maps to a rule the enforcer already implements.

## Verification

```pwsh
python -m pytest test_relabel_gate_audit.py -q
# 15 passed

python relabel_gate_audit.py
# wrote gate_audit_report_relabeled.json

python -c "import json; print(json.load(open('gate_audit_report_relabeled.json'))['gate_leaks_by_rule'].get('code_rules_other', 0))"
# 0
```
