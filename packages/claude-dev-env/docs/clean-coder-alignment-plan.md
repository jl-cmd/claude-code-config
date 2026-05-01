# Clean-Coder Agent Alignment Plan

This document captures the alignment between the `clean-coder` agent definition (`packages/claude-dev-env/agents/clean-coder.md`) and the local enforcement layer (`code_rules_enforcer.py` and companion blocking hooks). Companion to `agents-md-alignment-plan.md`, which performs the same exercise for `AGENTS.md`.

## Goal

The `clean-coder` agent is the canonical code-writing agent — the prompt it carries is what shapes generated code. For first-attempt writes to clear every hook gate, the agent prompt must internalize every rule the hooks enforce. Two-way alignment:

1. Every rule the hooks enforce at write time appears in the agent prompt so generated code clears each gate on the first write.
2. Every rule the agent prompt promises to satisfy is either (a) enforced by a hook, (b) listed as judgment (architectural / domain), or (c) tracked as a candidate hook addition.

## Methodology

- Read every `check_*` function in `packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py` (28 functions, lines 108–2236) plus `validate_content` dispatch (line 2239).
- Read every Write/Edit hook in `packages/claude-dev-env/hooks/hooks.json`, plus `windows_rmtree_blocker.py`, `gh_body_arg_blocker.py`, `sensitive_file_protector.py`, `mypy_validator.py`, `auto_formatter.py`.
- Read the AGENTS.md alignment plan (`packages/claude-dev-env/docs/agents-md-alignment-plan.md`) to keep the two surfaces consistent.
- Walked `clean-coder.md` section by section against the above.

## What this PR changes

### Tightened existing sections

- **Complete type hints**: added the `# type: ignore` ≥5-character trailing-reason format and explicit mypy-clean target.
- **Magic values → named constants**: extended to cover bare string structural literals (paths / URLs / regex anchors) and inline list/set literals of two-or-more constants in function bodies.
- **Constants location**: added the function-local `UPPER_SNAKE` advisory.

### New subsections in Inline Rule Reference

- **Library print() and CLI markers** — `print()` is allowed only under `/scripts/`, `_cli.py`, `/cli.py` path markers; the `check_library_print` hook fires elsewhere.
- **Test quality rules** — mock completeness, no `skip*` decorators on tests, no existence-only tests (`callable(x)` / `hasattr(...)` / `is not None`), no constant-equality tests, public-API testing only, React query priority (`getByRole > getByLabelText > getByText > getByTestId`), `userEvent` over `fireEvent`, mock at API boundaries, pragmatic five-point test-infra checklist, e2e spec test naming.
- **Required vs optional parameters** — the exact hook trigger: optional parameter where every call site passes the same value as the default.
- **Platform safety and external tools** — `shutil.rmtree` with `ignore_errors=True` blocked on Windows (with the canonical `force_rmtree` helper inlined), Node `mkdirSync({recursive: true})` for possibly-existing paths, `win32gui.X(.., None)` blocked, `gh ... --body-file` required.

### New section

- **Files Clean-Coder Does Not Create or Edit** — lock files, secret / credential files, scratch helpers (`scratch_*.py`, `debug_*.py`, `try_*.py`, `repro_*.py`), planning / audit artifacts (`docs/plans/*.md`, `*.plan.md`, `SESSION_STATE.md`, `*.audit.{json,md}`), image assets.

### Expanded tables and produce list

- **Hook-Enforced Rules** table grew from 7 rows to 30 rows, covering every blocking and advisory check the enforcer or sibling hooks emit.
- **What You Produce** added: mypy-clean, format matches `auto_formatter.py`, no `Any` / `# type: ignore` without ≥5-char reason, no platform pitfalls, no sensitive / lock / scratch files.

## Open items

### Category B — required by the agent prompt, no local hook (judgment items)

These are inherent to authoring code and not amenable to AST/regex enforcement. The prompt names them; satisfying them is the agent's judgment.

- Naming: `ctx`/`cfg`/`msg`/`btn`/`idx`/`cnt`/`elem`/`val`/`tmp` abbreviation expansion (the canonical-table form is in the prompt), `X_by_Y` map naming, preposition parameter prefixes, banned function-name prefixes (`handle_`/`process_`/`manage_`/`do_`), component naming for what they ARE.
- Structure: function length ≤ 15 lines (target) / 30 lines (hard), one abstraction level per function, guard clauses with zero `else` nesting, two-blank-line separation between Python top-level functions.
- Architecture: functions vs concrete classes vs ABCs, SOLID S/O/L/I/D, construction logic in models / services, self-contained components, `TODO:` on scaffolding.
- Data flow: reuse data already in scope; reuse-before-create constants (semantic duplication).
- Tests: pragmatic-infra five-point checklist (the prompt enumerates the five points; a hook would need new logic to verify each).
- Config: domain placement within `config/` (timing.py vs constants.py vs selectors.py); 0-reference dead-code constants.

### Category C — JS/TS asymmetry

`code_rules_enforcer.py` `validate_content` (line 2239) dispatches on file extension. For `.js`/`.ts`/`.tsx`/`.jsx`, only three checks run: `check_comment_changes`, `check_e2e_test_naming`, `advise_file_line_count`. Every other rule (magic values, naming, types, banned identifiers, boolean naming, parameter / return annotations, library print, optional-param-unused, `Any` detection) runs on Python files only.

For JS/TS code generated by clean-coder, the agent prompt is the only enforcement layer. The agent should still apply every rule from the prompt, but write-time hook coverage is materially weaker.

Out of scope for this PR.

## Recommended hook additions

Same list as the AGENTS.md alignment plan — the AST/regex-tractable Category B items, each scoped as its own small PR. Each closes a gap for both bugbot review (AGENTS.md) and clean-coder generation (this prompt) simultaneously.

| Item | Suggested check |
|---|---|
| Abbreviation identifier list | extend `BANNED_IDENTIFIERS` in `code_rules_enforcer.py` to include `ctx`, `cfg`, `msg`, `btn`, `idx`, `cnt`, `elem`, `val`, `tmp` |
| Map-naming `X_by_Y` rule | flag dict assignments whose target name lacks `_by_` |
| Preposition parameter prefixes | flag direction parameters lacking `from_` / `to_` / `into_` |
| Banned function-name prefixes | flag `def handle_*`, `def process_*`, `def manage_*`, `def do_*` |
| Function-length advisory | per-function line count; advisory above 30 |
| Sensitive-files extension | extend `sensitive_file_protector.py` to block `*.plan.md`, `SESSION_STATE.md`, `docs/plans/*.md`, `*.audit.{json,md}`, image extensions |
| Scratch-file name patterns | add `scratch_*.py`, `debug_*.py`, `try_*.py`, `repro_*.py` to the same protector |
| Config-domain placement | flag a constant added to `config/constants.py` whose name suggests `timing.py` or `selectors.py` |
| 0-reference dead-code constants | extend `check_file_global_constants_use_count` to flag 0 callers as well |

## Files in this PR

- `packages/claude-dev-env/agents/clean-coder.md` (modified) — adds the rules and sections listed above.
- `packages/claude-dev-env/docs/clean-coder-alignment-plan.md` (new) — this document.

## Verification

- Read updated `clean-coder.md` end-to-end and confirm each new section lands under the appropriate heading.
- Confirm every rule in the **Hook-Enforced Rules** table maps to a real check in `code_rules_enforcer.py` or sibling hook file.
- Confirm the inlined `force_rmtree` helper code block in **Platform safety and external tools** describes the unsafe-rmtree pattern without containing the exact match-string the `windows_rmtree_blocker.py` hook scans for. Otherwise the hook would block any future edit to the file.
- No code changes — the agent prompt and plan doc are documentation only.

## Out of scope

- Closing the Category B judgment items via prompt rewrite (they are inherent to authoring code).
- Implementing any of the recommended hook additions (each is its own small PR).
- Investigating JS/TS hook coverage parity (Category C — would require a JS/TS parser the project does not yet vendor).
- Changes to `code_rules_enforcer.py` or any other hook source file.
