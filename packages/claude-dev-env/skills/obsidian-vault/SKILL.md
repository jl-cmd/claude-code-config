---
name: obsidian-vault
description: >-
  On-demand Obsidian vault context retrieval via the configured mcp__obsidian__*
  server. Search sessions/, decisions/, and Research/ before substantive project
  work. Triggers: obsidian-vault, session context, vault search, prior decisions.
---

# Obsidian Vault

## Overview

This skill captures the `<obsidian_vault>` policy from
`~/.claude/system-prompts/software-engineer.xml` so it can be loaded on demand
instead of remaining always-on in the system prompt. Invoke it when prior
session history, decisions, or research from the Obsidian vault would change
how the current task is executed.

The retrieval *mechanics* live in `/recall`. The
`vault_context_retrieved` frontmatter bookkeeping lives in `/session-log`
Step 2. This skill's job is to make the vault search happen at the right
moments so the downstream flag can be set honestly.

## Trigger Conditions

Invoke automatically when any of the following holds:

- Starting substantive project work in a new session.
- The user references prior work, prior decisions, or prior context.
- A task might repeat or reverse a prior decision.
- Context is needed on *why* something was built a certain way.
- The user encounters a component or system with known history.

If none of these apply, skip the skill. Trivial questions, one-off scripts,
and pure-reference lookups do not need vault context.

## Search Algorithm

1. **Search by frontmatter first.** Call `mcp__obsidian__search_notes` with
   `searchFrontmatter: true` and the project name (inferred from the git
   remote, working directory, or topic under discussion). Then search by
   content keywords such as `blocked`, `superseded`, `decision`, `gotcha`,
   plus task-specific terms (component names, error messages, library names).

   Concrete example:

   ```
   mcp__obsidian__search_notes({ query: "claude-code-config", searchFrontmatter: true })
   mcp__obsidian__search_notes({ query: "superseded decision themes-pr-stack" })
   ```

2. **Scope to the three vault folders.**
   - `sessions/` — session reports (`type: session-report`, `project`,
     `session`, `date`, `status`, `blocked`, `tags`).
   - `decisions/` — decision notes (`type: decision|procedural|fact|gotcha`,
     `project`, `date`, `status: Active|Superseded`, `tags`).
   - `Research/` — deep research documents.

3. **Read the top 3–5 hits.** Use `mcp__obsidian__read_note` for single notes
   or `mcp__obsidian__read_multiple_notes` for several at once. Prefer recent
   notes over older ones, and prefer decision notes and session summaries
   over raw research.

4. **Summarise the relevant prior context** inline before proceeding with
   the work, so the user can see what prior history shaped the current
   approach. Call out any decision marked `status: Superseded`.

5. **Record the outcome for `/session-log`.** Set
   `vault_context_retrieved: true` if any `mcp__obsidian__*` read or search
   tool was used productively (at least one relevant note surfaced and
   informed the work). Set it to `false` if the vault was unreachable or no
   relevant notes were found.

## Session-End Integration

At the end of substantive sessions, offer to run `/session-log`. Step 2 of
`/session-log` already auto-detects vault MCP calls and writes the
`vault_context_retrieved` field into frontmatter. This skill's contribution
is to ensure those MCP calls actually happen when they should, so the flag
ends up `true` whenever genuine prior context exists.

## Frontmatter Requirement

Any session note written via `/session-log` after invoking this skill must
include:

```yaml
vault_context_retrieved: true   # or false
```

`true` means a `mcp__obsidian__*` read or search tool was used productively
during the session. `false` means the vault was unreachable or no relevant
notes existed.

## Vault Location

The vault is accessed entirely through the `mcp__obsidian__*` MCP server.
Its filesystem location comes from the MCP server's own configuration (or
the `OBSIDIAN_VAULT_PATH` environment variable when a caller needs to
resolve it outside the MCP server). This skill does not read the filesystem
directly and must not hard-code vault paths in code it produces — resolve
the path at run time from the server or environment.

## Reference

- Policy source: `~/.claude/system-prompts/software-engineer.xml`, section
  `<obsidian_vault>`.
- Related skills: `/recall` performs the retrieval mechanics end-to-end with
  user-facing output; `/session-log` consumes the `vault_context_retrieved`
  flag this skill is responsible for keeping honest.
