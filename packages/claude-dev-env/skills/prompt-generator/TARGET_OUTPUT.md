# prompt-generator — user-visible output contract

This file is the **target output spec** for eval-driven iteration of the `prompt-generator` skill. Evals assert behavior against it; update this document and `SKILL.md` together when the contract changes.

**Methodology:** [Anthropic — Agent Skills: evaluation and iteration](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration)

## User-visible output contract

- **Questions:** All clarifying questions go through **AskUserQuestion** — never as direct chat text.
- **Options:** Each question offers **2–4** options; the **recommended** option is listed **first**. Options populated from discovery findings are labeled **`[discovered]`**.
- **Final delivery (exactly three parts, in order):**
  1. One-line audit status: `Audit: pass 14/14` or `Audit: fail N/14 — [reason]`
  2. The XML prompt artifact in a **single** fenced code block (language tag `xml` recommended)
  3. **Nothing else** — no commentary, prose wrap-up, tables, or extra fences

- **Full audit table:** Surfaces **only** on an explicit debug request from the user (e.g. “show debug”, “full audit table”).
- **Hook retries:** Invisible to the user — handled inside the subagent / internal loop.
- **Hook rejections:** At most a **one-line** status note (e.g. `Retrying: scope anchor missing`) — never full hook output or retry diffs in user-visible text.
- **Decision stability:** When choosing an approach during generation, **commit** and see it through. Do not revisit decisions unless **new information** contradicts prior reasoning. Course-correct later if the chosen approach fails.

## Scenario 1: Fresh chat with brief goal

**Trigger:** `/prompt-generator [brief goal]` in a new or near-empty session.

**Discovery:** **3–5** parallel **Glob/Grep** (or equivalent repo search) calls targeting the task domain. Identify repo structure, relevant packages, configs, existing patterns.

**Q&A:** A **single** AskUserQuestion with **2–4** questions. Cover scope, audience, output format, constraints. Options populated from discovery where possible.

**Output:** One-line audit + fenced XML prompt. Nothing else.

## Scenario 2: Session handoff

**Trigger:** `/prompt-generator` when the session already has substantial prior context; user wants a prompt for a **new** session to continue work.

**Discovery:** Read **conversation context** — **no** external tool calls **needed** for facts already stated. Extract current state, decisions, files touched, next steps, active constraints.

**Q&A:** A **single** AskUserQuestion with **1–2** questions (lighter than Scenario 1): e.g. what the new session should prioritize, what to exclude.

**Output:** One-line audit + fenced XML prompt. Nothing else.

**Handoff prompt quality:** `<context>` must make the artifact **self-contained** (new session can resume without prior chat). Preserve prior **decisions** explicitly, not only paraphrased goals.

## Scenario 3: Long unstructured input

**Trigger:** User pastes a long, multi-requirement request (paths, tools, process constraints).

**Discovery:** Verify references from the input (e.g. packages, `shared_utils`, config patterns) with targeted tool calls **before** AskUserQuestion when the repo can disambiguate.

**Q&A:** First AskUserQuestion question **confirms extracted intent** — not generic. Ambiguities as **specific** options, not open-ended prompts.

**Requirements:** **All** stated requirements must appear in the generated prompt (none dropped): e.g. timeouts, selectors, config extraction, TDD, code rules, test safety.

**Output:** One-line audit + fenced XML prompt. Nothing else.

## Scenario 4: Noisy context, no degradation

**Trigger:** `/prompt-generator ...` after a long, noisy thread (unrelated topics, failed tools, tangents).

**Output shape:** Same as Scenario 1 — one-line audit + single fenced XML block.

**Content:** The XML must address **only** the prompt-generator request (e.g. code review + security). **No** contamination from prior errors, tangents, or unrelated tool failures.

**Structure:** XML **complete and well-formed** — no truncation under context pressure.

**Delegation:** Prompt generation runs in a **subagent** with **curated** context — not the raw full conversation dump.

## Structural invariant A — No tool calls after fence opens

- No `tool_use` / tool blocks **after** the first opening fence (`` ``` ``) of the prompt artifact in the **final** user-visible assistant message.
- **Order:** All discovery tool calls → AskUserQuestion → then emit **one uninterrupted** response containing audit line + fenced artifact.

## Structural invariant B — Fenced block closes cleanly

- Opening fence has a matching closing fence.
- Every XML tag properly opened and closed.
- No truncation at numbered-list bullets; no mid-sentence cuts; no incomplete sections.
- Artifact is copy-pasteable as-is.

## Structural invariant C — Discovery complete before generation

- When the user is uncertain where logic lives, **attempt discovery** to locate it **before** generating the final XML.
- If resolved: prompt references **concrete paths** from discovery.
- If unresolved: include `<open_question>` in `<context>` for the downstream agent.
- **No re-entry to discovery** after the fenced block has started.

## Structural invariant D — No mid-artifact hedging

- Inside the fenced XML: **no** phrases like “let me also check”, “actually”, “one more consideration”.
- **No** tentative language (“might be”, “possibly”, “I think”) in `<instructions>` or `<constraints>`.
- Express uncertainty with **`<open_question>`** tags, not inline hedges. Instructions read as **confident, complete**, not draft-in-progress.

## XML artifact (minimum sections)

The fenced prompt **must** include at least:

- `<role>...</role>`
- `<context>...</context>`
- `<instructions>...</instructions>`
- `<constraints>...</constraints>`
- `<output_format>...</output_format>`

Optional: `<examples>`, nested tags, or additional sections when the task requires them.

## Internal 14-point checklist (audit numerator)

The `14` in `Audit: pass 14/14` refers to the skill’s internal checklist rows (scope, instructions, safety, output contract, etc.). **Do not** print the full table unless the user requests debug output. On failure, the one-line reason should name the **primary** failing theme (e.g. “scope anchor missing”, “incomplete XML”).
