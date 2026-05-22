# Sources

Every load-bearing design decision in this skill traces back to one of
the citations below. Quoted text is verbatim from the source unless
otherwise noted.

## Table of contents

1. [PreCompact hook specification](#precompact-hook-specification)
2. [Effective context engineering (Anthropic)](#effective-context-engineering-anthropic)
3. [Effective harnesses for long-running agents (Anthropic)](#effective-harnesses-for-long-running-agents-anthropic)
4. [Context engineering cookbook (Anthropic)](#context-engineering-cookbook-anthropic)
5. [Third-party corroboration of stdout-as-instructions behavior](#third-party-corroboration-of-stdout-as-instructions-behavior)

## PreCompact hook specification

URL: https://code.claude.com/docs/en/hooks (canonical, after the 301
redirect from `docs.claude.com/en/docs/claude-code/hooks`).

Load-bearing quotes:

> `PreCompact`, `PostCompact`: what triggered compaction — `"manual"`,
> `"auto"`

Drove: matcher value `"manual|auto"` in `hooks.json`.

> `PreCompact` — Top-level `decision` — `decision: "block"`, `reason`

Drove: gotcha "Exit code 2 BLOCKS compaction. This skill never returns 2."

> SessionStart, Setup, SubagentStart — Context only —
> `hookSpecificOutput.additionalContext` adds context for Claude... No
> blocking or decision control

Drove: gotcha "No `hookSpecificOutput.additionalContext` for PreCompact."
PreCompact is not in the "Context only" category, confirming the channel
is unavailable for this event.

Common-input-fields quote:

> `session_id`: Current session identifier
> `transcript_path`: Path to conversation JSON
> `cwd`: Current working directory when the hook is invoked
> `permission_mode`: Current permission mode
> `hook_event_name`: Set to `"PreCompact"`
> `trigger`: Either `"manual"` or `"auto"` indicating what initiated
> compaction

Drove: the stdin shape the hook parses.

## Effective context engineering (Anthropic)

URL: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

Load-bearing quotes:

> Find the smallest set of high-signal tokens that maximize the
> likelihood of your desired outcome.

Drove: the ~500-token budget on the directive, the deliberate omission
of synthesized prose.

> Start by maximizing recall to ensure your compaction prompt captures
> every relevant piece of information from the trace, then iterate to
> improve precision by eliminating superfluous content.

Drove: the explicit MUST PRESERVE / CAN DROP split. Recall is handled by
the preserve list; precision is handled by the drop list.

> Compaction is the practice of taking a conversation nearing the
> context window limit, summarizing its contents, and reinitiating a new
> context window with the summary.

Drove: framing throughout — the hook's job is to shape the summary, not
to shape what the next session does after the summary lands.

## Effective harnesses for long-running agents (Anthropic)

URL: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

Load-bearing quotes:

> A structured JSON file with a list of end-to-end feature descriptions

Drove: state files as structured JSON, not markdown — the model is less
likely to inappropriately rewrite JSON.

> The model is less likely to inappropriately change or overwrite JSON
> files compared to Markdown files.

Drove: the state-file contract specifying JSON.

> Maintain lightweight identifiers (file paths, stored queries, web
> links, etc.) and use these references to dynamically load data into
> context at runtime using tools.

Drove: the RESUMPTION HINT block. The compactor preserves the pointer;
the next session does the heavy re-load.

## Context engineering cookbook (Anthropic)

URL: https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools

Load-bearing quotes:

> **MUST PRESERVE:**
> 1. Every quantitative lifespan figure with its source organism
> 2. Every effect size from interventions with the organism and context
> 3. Which documents have been read (by path)
> ...
> **CAN DROP:**
> - Exact wording of earlier model outputs
> - Appendix table cell values
> - Intermediate search queries that were not productive

Drove: the literal MUST PRESERVE / CAN DROP block structure. The
cookbook validates this shape with the cookbook's own probe — high-level
labeled facts survive compaction; obscure specifics drop.

Cookbook probe outcome (paraphrased): on a research-agent trace,
high-level facts with labels were preserved 3/3 across compaction;
obscure specifics dropped 3/3. The directive mirrors what survived.

## Third-party corroboration of stdout-as-instructions behavior

The official Anthropic docs at `code.claude.com/docs/en/hooks` do not
explicitly state that PreCompact stdout becomes custom compact
instructions. Two corroborating sources confirm this behavior:

1. **Dickson Tsai (Claude Code engineer), via X post** referenced in web
   search results: "Got a new PreCompact hook for you all to try in
   Claude Code v1.0.48! You can have your hook script append to the
   built-in instructions after reading the transcript. The input will
   say whether the compact was 'manual' (run from /compact) or 'auto'
   (from full context)." URL:
   https://x.com/dickson_tsai/status/1943354030903975939

2. **disler/claude-code-hooks-mastery** GitHub repo, PreCompact section:
   "Payload: trigger ('manual' or 'auto'), custom_instructions (for
   manual), session info. Enhanced: Transcript backup, verbose feedback
   for manual compaction." Confirms the `custom_instructions` field on
   the stdin payload during manual triggers.

Drove: the entire premise of the hook. Without this behavior the hook
would be a no-op.
