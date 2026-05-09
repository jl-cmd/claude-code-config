# Output contract

The skill emits exactly one artifact: the rewritten prompt. The emission shape depends on how the input arrived.

## Emission modes

**Paste mode** — input arrives as the user's message body or as a fenced block within it. Emit one fenced block containing the rewritten prompt. Use a fence with at least four backticks so any inner triple-backtick code blocks in the rewritten prompt do not prematurely close the outer fence:

``````
````
<rewritten prompt>
````
``````

**File-path mode** — input arrives as a file path argument (e.g., `/structure-prompt path/to/file.md`). Rewrite the file in place. Emit a confirmation that names the file, gives the line-count delta, and lists the spokes that fired. When gaps exist, the confirmation also lists them — the output may span multiple lines.

## Disposition invariants

**No silent action** (also referenced as "no silent no-op"). Every spoke that fires MUST record its action. Two cases use the same `> Gap:` mechanism:

- **Deferred.** The spoke elected not to apply its transformation — missing source, ambiguous detection, fallback to user input, carve-out match, or any other reason. The gap note records what was deferred and why.
- **Applied.** The spoke successfully applied its transformation. The gap note records what changed (e.g., persona transformed, directive replaced, citation added) so the reader can detect the change.

Silent omission is never the correct disposition in either case. The reader of the output must always be able to detect which spokes fired, which deferred, and why.

## Preservation invariants

Two clauses govern what the rewritten prompt may change.

**Existing input content is preserved byte-for-byte.** The rewrite must not alter any of these values when they already appear in the input:

- Identifiers (variable names, function names, file paths)
- IDs and SHAs
- ID prefixes
- Proper names (people, products, services)
- Numeric values (line numbers, thresholds, counts)
- URLs
- Code block contents

**New numeric criteria are additive content.** When a spoke introduces a new measurable threshold (e.g., the `≥3` adversarial probes from [`per-category.md`](per-category.md), the citation-occurrence cutoffs from [`citation-depth.md`](citation-depth.md), or any new word/probe/count limit), that number is sourced per the authorized-additions list below. New numeric criteria augment the prompt; they never overwrite a numeric value the input already carries.

## Idempotency

A second invocation of the skill on its own output produces the same output. Some spoke detection patterns (e.g., structure ordering, per-category disposition insertion) remain true on every invocation — the input shape doesn't change. But detection conditions for content-mutating spokes incorporate an "already applied" check: placeholders no longer match because they've been substituted; identifier mentions no longer match because citations have been added; the canonical sub-bucket no longer matches because the ⭐ marker is now present; the adversarial phrase no longer matches because the noun is specific. Combined with the gap-report block's deterministic replacement (current run overwrites, prior-run blocks are preserved as passthrough when no new gaps exist), the full pipeline produces identical output on re-invocation.

## Authorized additions

The skill adds content only when a spoke explicitly authorizes it. Evidence-required additions (cited values from the rubric, placeholder values from the input or user) must also pass [`research.md`](research.md) confirmation that the new content matches a real source (rubric, sibling artifact, user-pasted context, or AskUserQuestion answer). Skill-defined additions (the per-category disposition line, surface-formatting cleanup, the failure-mode noun from the adversarial-tuning built-in lookup table) are authorized by their spoke firing alone. The authorized additions are:

- The mission line, when [`persona.md`](persona.md) replaces a role assignment
- The per-category disposition line, when [`per-category.md`](per-category.md) detects an unenforced framework
- Measurable criteria, when [`directives.md`](directives.md) or [`constraints.md`](constraints.md) replaces a soft directive
- Real values in place of placeholders, when [`instantiation.md`](instantiation.md) fires
- `file:line` citations on identifier mentions, when [`citation-depth.md`](citation-depth.md) fires
- The ⭐ canonical-case marker on one sub-bucket, when [`canonical-case.md`](canonical-case.md) fires
- A category-specific failure-mode noun in the adversarial-pass phrase, when [`adversarial-tuning.md`](adversarial-tuning.md) fires
- Surface-formatting normalization (typo correction, single bullet style, language tags on fenced blocks, trimmed trailing whitespace, collapsed blank-line runs, sequential heading levels), when [`cleanup.md`](cleanup.md) fires

Skill-defined additions (the per-category disposition line, surface-formatting cleanup, the failure-mode noun from [`adversarial-tuning.md`](adversarial-tuning.md)'s built-in lookup table) are authorized by their spoke firing alone — they do not need an external source. For evidence-required additions (cited values from the rubric, placeholder values from the input or user), [`research.md`](research.md) confirms the new content matches a real source. When evidence is missing for an evidence-required addition, the spoke leaves the prompt as-is and reports the gap. For a skill-defined addition, the spoke fires unconditionally and STILL emits an action note recording what changed — the "No silent action" invariant applies to both applied and deferred outcomes. The gap-report shape depends on emission mode:

- **Paste mode.** The fenced block contains exactly the rewritten prompt — no footer follows it. Record gaps inside the fenced block as a final blockquoted note prefixed `> Gap:` (one line per gap). The note sits below the rewritten prompt's last block and remains inside the fence.
- **File-path mode.** The rewritten file on disk MUST be self-describing for gaps. Append a final HTML comment block at the bottom of the file. The block opens with `<!-- gap-report:` on its own line, contains one `> Gap:` line per gap, and closes with `-->` on its own line. When no gaps exist AND no existing `<!-- gap-report:` block from a prior run is present, omit the comment block entirely. When an existing `<!-- gap-report:` block from a prior run is present, the block is preserved as passthrough (not duplicated) even if the current run has no gaps — the bullet in [`block-classification.md`](block-classification.md) step 3 treating gap-note lines as passthrough ensures the prior-run block survives idempotently without being re-tagged or removed. The block is deterministically replaced (not accumulated) when the current run produces gaps: a new `<!-- gap-report:` block reflecting only the current run's gaps overwrites the prior block. Example for a run with two gaps:

  ```
  <!-- gap-report:
  > Gap: Persona transformed — original "You are an expert code reviewer" replaced with mission "Find bugs in this code."
  > Gap: canonical-case marker skipped — framework has 5+ sub-buckets but rubric match, bullet density, and identifier density found no clear canonical case
  -->
  ```

  The post-edit confirmation message that names the file and the spokes that fired ALSO lists the same gaps, but the file itself is now self-describing — a reader of the file alone can detect which spokes deferred and why.
