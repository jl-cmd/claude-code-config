# Prompt Workflow Hook Specs

Deterministic runtime gates for prompt workflows.

## Gate: Execution handoff + scope anchors (PreToolUse Task/Agent)

- Hook: `hooks/blocking/agent-execution-intent-gate.py`
- Event: `PreToolUse`
- Matcher: `Task|Agent`
- When it applies: only if the combined task `description` and `prompt` contain the real slash command token `/agent-prompt` (native Agent/Task tools have no intent metadata fields).
- Fail condition (when the gate applies):
  - Missing required scope anchors in the same combined text:
    - `target_local_roots`
    - `target_canonical_roots`
    - `target_file_globs`
    - `comparison_basis`
    - `completion_boundary`
- When it does not apply: launches without `/agent-prompt` pass through with no checks from this hook.
- Action: `deny` with concrete missing requirement list.

## Gate: Leakage + Checklist + Scope (Stop)

- Hook: `hooks/blocking/prompt-workflow-stop-guard.py`
- Event: `Stop`
- Fail condition:
  - Raw internal refinement object appears in assistant output without explicit debug intent
  - Prompt-workflow response detected but deterministic checklist container is missing
  - Prompt-workflow response detected and required deterministic checklist rows are missing
  - Prompt-workflow response detected and required scope anchors are missing
  - Prompt-workflow response detected and runtime context-control signals are missing
  - Scope-bound text uses banned ambiguous scope terms
- Action: `block` with correction reason.

## Required Scope Anchors

- `target_local_roots`
- `target_canonical_roots`
- `target_file_globs`
- `comparison_basis`
- `completion_boundary`

## Required Deterministic Checklist Rows

- `structured_scoped_instructions`
- `sequential_steps_present`
- `positive_framing`
- `acceptance_criteria_defined`
- `safety_reversibility_language`
- `reversible_action_and_safety_check_guidance`
- `concrete_output_contract`
- `scope_boundary_present`
- `explicit_scope_anchors_present`
- `all_instructions_artifact_bound`
- `scope_terms_explicit_and_anchored`
- `completion_boundary_measurable`
- `citation_grounding_policy_present`
- `source_priority_rules_present`

## Runtime Context-Control Signals

- `base_minimal_instruction_layer: true`
- `on_demand_skill_loading: true`

These two signals are runtime-checked by the Stop guard whenever a prompt-workflow response is detected.

## Deterministic Boundary

These hooks enforce only structural/runtime checks. Semantic quality remains in auditor layer.
