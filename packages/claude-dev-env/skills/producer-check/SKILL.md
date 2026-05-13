---
name: producer-check
description: Verifies producer/consumer agreement for a new sentinel/enum literal. Takes a field name plus the expected literal value (and optionally the consumer constant name) and returns the literal each producer site actually emits to that field across the repo. Caller compares the producers' literals against the expected value and fixes mismatches in the same diff to close Category K (Codebase conflicts). Backbone: zoekt MCP for fast cross-repo search, serena MCP find_referencing_symbols for the consumer cross-check. Triggers on "/producer-check", "verify producer/consumer agreement", "find producers of X", any clean-coder Diff Impact Analysis Parallel Sites or Conflict Pairs bullet naming a new sentinel literal, Self-Audit Loop iteration surfacing Category K.
---

# producer-check

Verify every producer of a field emits the literal the consumer expects. Backed by zoekt + serena.

## Gotchas

- Search three producer patterns: dict construction (`"source": "main"`), dataclass / `NamedTuple` instantiation, and bare tuple position (`(title, price, "main")`). Each carries a different regex shape.
- Tag string-formatted producers (`f"{prefix}main"`, `f"{kind}_source"`) as `dynamic` and surface them separately. The literal value is computed at runtime; the caller resolves the format string by hand.
- Sort producers by file family before reporting: production source first, tests second, fixtures third. The caller treats each family on its own footing.
- Index every literal value the field carries even when it matches the expected one. Coverage of the full producer set proves the agreement check ran end-to-end.
- Cross-check via serena: feed the consumer constant's name to `find_referencing_symbols` so every comparator site (`if x == CATALOG_SOURCE_PRIMARY:`) appears alongside the producer-emit sites. Conflict pairs surface when the comparator branch handles a literal no producer emits.

## When this skill applies

- clean-coder Diff Impact Analysis Parallel Sites or Conflict Pairs bullet names a new sentinel / enum / status string.
- clean-coder Self-Audit Loop surfaces Category K (producer/consumer disagreement, K1 conflict, K6 docstring/implementation).
- `/producer-check <field_name> <expected_value>` or `/producer-check <field_name> <expected_value> <consumer_constant_name>`.

**Refusals — first match wins; respond with the quoted line and stop.**

- Missing field name or expected value: `Need a field name and expected value. Re-invoke with /producer-check <field_name> <expected_value> [<consumer_constant_name>].`
- Zoekt repo index not loaded: `Zoekt has no index for this repository. Run mcp__zoekt__list_repos to confirm coverage, then re-invoke.`
- Serena project inactive (only when a consumer constant name is supplied): `Serena project not active. Activate with mcp__serena__activate_project, or re-invoke without the consumer constant.`

## Process

```
[ ] Step 1: Search producers via zoekt
[ ] Step 2: Extract the literal emitted at each producer
[ ] Step 3: Cross-check the consumer (when constant name supplied)
[ ] Step 4: Return the producer / mismatch table
```

### Step 1 — Search producers via zoekt

Run one search per producer pattern. Quote the field name and one of the three producer shapes:

```
mcp__zoekt__search(query="<field_name>:\\s*[\"']", limit=100)
mcp__zoekt__search(query="\\(.*,\\s*[\"'][^\"']+[\"']\\)\\s*#.*<field_name>", limit=100)
mcp__zoekt__search(query="<field_name>\\s*=\\s*[\"']", limit=100)
```

Merge the result lists by `file:line`. Each match becomes a candidate producer.

### Step 2 — Extract the literal at each producer

For every candidate, read the matched line (and one line of context above) and capture the literal value. Tag the producer:

- **`literal`** — value is a string literal in quotes; record the literal verbatim.
- **`dynamic`** — value is built from an f-string, concatenation, or function call. Record the source expression so the caller can resolve the runtime value.
- **`constant`** — value is an UPPER_SNAKE reference (e.g. `CATALOG_SOURCE_PRIMARY`). Record the constant name.

### Step 3 — Cross-check the consumer (optional)

When the caller supplied `<consumer_constant_name>`, run:

```
mcp__serena__find_referencing_symbols(
  name_path="<consumer_constant_name>",
  relative_path=".",
)
```

Each result is a comparator site. Note the literal the comparator's `if`/`elif`/`match` branch expects. Any branch literal absent from the producer-emit set indicates a Category K conflict.

### Step 4 — Return the producer / mismatch table

| Producer file:line | Literal kind | Emitted value | Match? |
|---|---|---|---|
| `google_sheets_loader.py:47` | literal | `"main"` | mismatch (expected `"primary"`) |
| `analysis_pipeline.py:59` | constant | `CATALOG_SOURCE_PRIMARY` | match |
| `sheets_service.py:388` | literal | `"main"` | mismatch (expected `"primary"`) |

Append a coverage line summarizing total producers, matches, mismatches, and dynamic sites.

Empty producer set: `No producers found for field <field_name>. Verify the field name and re-invoke, or treat <consumer_constant_name> as orphan via /orphan-check.`

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This skill — invocation, process, output, refusals. |

## Folder map

- `SKILL.md` — single-file skill. Execution delegates to `mcp__zoekt__*` and `mcp__serena__*` tools.
