---
name: session-log
description: >-
  Log a session report by handing the HTML authorship to doc-gist (which designs fresh per session and auto-publishes via the `<!-- @publish-as-gist -->` marker hook), then track vault context, extract unrecorded decisions, tidy the project's session folder, and output a /rename command. Use when the user says /session-log, journal this session, log this work, session report, or any variation of "summarize/log/record this session". Also triggers on "save session", "capture session", or "document what we did".
---

# Session Log

## Overview

The HTML artifact is doc-gist's job end-to-end. Session-log owns everything around it: where the file lives in the vault, what number it gets, the frontmatter metadata contract, post-write vault tracking, decision extraction, project-folder hygiene, and the closing `/rename` hand-off.

**Announce at start:** "I'm logging this session."

## Why this skill delegates HTML to doc-gist

Sessions come in many shapes — convergence loops, feature builds, research dives, incidents, refactors, decisions. A single h2-emoji-list template forces every session into the same form regardless of fit, and the artifact reads as a process log rather than a substance log. Doc-gist's principle: *"design fresh per request, drawing on a gallery of 20 HTML shape patterns."* Each session report gets the shape that fits the session.

The gallery lives at `~/.claude/skills/doc-gist/references/examples/`. Patterns that usually fit session reports:

| Session character | Gallery shape to study |
|---|---|
| Feature build / PR ships | `17-pr-writeup.html` |
| Incident, debugging arc, convergence loop | `12-incident-report.html` |
| Status update / weekly progress | `11-status-report.html` |
| Implementation plan or decision record | `16-implementation-plan.html` |
| Exploration of multiple approaches | `01-exploration-code-approaches.html` |
| Code-explainer with module map | `04-code-understanding.html` |

The session designer reads the matching gallery file, then designs the report in that shape. **Adapt, do not copy.**

## Gotchas

- **Doc-gist's auto-publish hook fires on Write/Edit of any HTML containing `<!-- @publish-as-gist -->`.** Session-log composes the HTML with the marker so auto-publish runs by default — sessions are intended for sharing with collaborators. The hook prints the gist + preview URLs to tool output; capture both.
- **`gh` must be authenticated.** Auto-publish runs `gh gist create`. If `gh` is unauthenticated, `gh gist create` writes its error to stderr; the hook surfaces that message and exits 0 (does not block the Write). Surface the error to the user; the local vault HTML is still the canonical artifact, so the remaining steps still run.
- **Vault paths sit outside `.claude/`.** Headless vault paths (e.g., `$OBSIDIAN_VAULT_PATH`) resolve outside the project tree. The `md_to_html_blocker` PreToolUse hook blocks `.md` writes unless the path is exempt — exemptions include any path containing `/.claude/` and README/CHANGELOG files at repo root. Session reports use HTML, which the hook ignores entirely.
- **Sessions describe current state by convention.** The state_description_blocker hook does not scan .html, but the rule at `~/.claude/rules/no-historical-clutter.md` applies as a writing standard — skip historical and comparative language when composing the report; the rule file lists the full trigger set.
- **`write_existing_file_blocker` rejects Write on existing paths.** Use Write only when creating a fresh session report; use Edit for the vault-context append in step 3.
- **Each Write/Edit of the marked HTML creates a fresh gist with a new ID.** `gist_upload.py` calls `gh gist create` with no lookup of any prior gist, so step 3's Edit produces a different gist URL than step 2's Write. Quote the URLs from the FINAL publish (the one that fires after step 3's Edit) to the user; never embed a step-2 URL inside the HTML that step 3 then re-publishes.
- **Obsidian frontmatter index is HTML-blind.** Obsidian's native YAML-frontmatter parser reads only `.md` files. HTML files do not appear in Obsidian's frontmatter index. Search by content still works; search by `type: session-report` does not.

## Backend Detection (run before Step 1)

Determine which storage backend is available. First success wins.

1. **Headless vault** — Bash `ob --version` to verify the obsidian-headless CLI is installed. Check `OBSIDIAN_VAULT_PATH` env var or `~/.claude/vault/` for a vault directory. When the CLI check succeeds AND at least one of those paths resolves to a vault directory, set `backend = "headless"`.
2. **Local vault** — fall back to `~/.claude/vault/`. Create `~/.claude/vault/sessions` via `mkdir -p` if missing. Set `backend = "local"`.

**Session-number detection:** Bash `ls` the project's session folder, parse filenames matching `[N]. *.html` or `[N]. *.md` to preserve sequence across the format migration. Highest N + 1. New project → start at 1.

**Output paths:**
- headless: `$OBSIDIAN_VAULT_PATH/sessions/[Project]/[N]. [Title].html` (falls back to `~/.claude/vault/` when the env var is unset)
- local: `~/.claude/vault/sessions/[Project]/[N]. [Title].html`

Announce the backend: "Using headless vault at [path]." or "Using local vault at ~/.claude/vault/. Install obsidian-headless and set $env:OBSIDIAN_VAULT_PATH to enable sync."

---

## Step 1: Compose Session Metadata

Review the conversation to identify the session's primary outcome and the small set of facts a cold reader needs.

Resolve the metadata used by the frontmatter and the vault path:

- **Project name:** infer from conversation context
- **Session number:** from backend detection above
- **Date:** today's date
- **Title:** a 2–5 word summary of the session's primary outcome. Examples: "Amazon Auth Migration", "Source Loading Fix", "PR 475 Convergence". Avoid generic titles like "Bug Fixes".

The frontmatter contract every session report carries (inside an HTML comment, as the first child of `<body>`):

```html
<!--
type: session-report
project: [name]
session: [N]
date: [YYYY-MM-DD]
status: completed|in-progress|blocked
blocked: true|false
vault_context_retrieved: true|false
tags: [session, [project-tag], [topic-tags]]
-->
```

Every session report carries this metadata block verbatim so vault search and the tidy step in step 5 work.

## Step 2: Compose the HTML via doc-gist's shape principles

Design the artifact for **this session's character**, drawing on the doc-gist gallery patterns listed above. The report must answer for a cold reader, from the H2 headers alone, three questions: *what shipped*, *why it matters*, *what impact it had*. Process narration (commit-by-commit walks, agent gotchas, retry counts) belongs at the end, not in the opening sections.

**Required somewhere in the HTML (commonly in `<head>`):** the auto-publish marker.

```html
<!-- @publish-as-gist -->
```

The marker triggers the PostToolUse hook after Write or Edit — the hook scans the entire HTML for the literal sentinel string and uploads the file to a secret gist, then prints the gist + preview URLs to your tool output. The marker must be the literal comment text exactly; whitespace inside breaks it.

**Required at the top of `<body>`:** the frontmatter HTML comment from step 1.

**Required as the first content section:** an opening "What this session shipped" paragraph + bullets — written so a reader with zero prior context understands the outcome. For continuation sessions (where the substantive work landed in a prior session), recap the parent session's outcome briefly so the report stands alone.

**Required: self-contained HTML.** Inline `<style>`, no external CSS/JS, no `./relative/paths`. Doc-gist's transport sends one file; external refs fail to load in the preview.

Beyond those four requirements, design the shape that fits. A convergence loop session reads naturally as an incident timeline (`12-incident-report.html`); a feature build reads as a PR writeup (`17-pr-writeup.html`); a research session reads as a feature explainer (`14-research-feature-explainer.html`). Read the matching gallery entry for typography, palette, spatial idioms — adapt, do not copy.

**Write the file** via the Write tool to the vault path. Create the project directory via `mkdir -p` if it does not exist. The auto-publish hook fires after the Write completes and prints a gist + preview URL pair to stderr. Step 3's Edit triggers the hook again and prints a fresh pair. Always quote the URL pair from the **most recent auto-publish run for the session being created** — for the just-created session that is step 3's pair (the step-2 gist becomes orphaned the moment step 3 republishes). Note: Step 5's tidy audits every `.html` file in the project folder including the just-created session, so if Step 5's frontmatter auto-fix touches the current session, the Step 5 republish URL pair becomes the new canonical pair for that session (re-quote it to the user with a "Session republished — new preview: <url>" line). The Step 3 URL pair stays canonical only when Step 5 does not touch the current session.

**If the Write fails**, output the HTML content in the conversation so the user can copy it manually. Skip step 3 and continue at step 4.

## Step 3: Vault Context Tracking

This step runs automatically after step 2.

Review the conversation history for any use of these vault MCP tools (excluding this skill's own calls during step 2):

- `mcp__obsidian__search_notes`
- `mcp__obsidian__read_note`
- `mcp__obsidian__read_multiple_notes`

Edit the vault HTML via two Edit calls (each Edit re-fires the auto-publish hook and creates a fresh gist; **the URL pair from the second/final Edit is canonical** — the first Edit's URLs are orphaned the moment the second Edit lands):

1. Set the frontmatter `vault_context_retrieved` field to `true` when any of the three tools fired this session, `false` otherwise.
2. Append one fact — vault-context status — into whatever section the report designer placed for notes / metadata / references. If the report has no such section, append a fresh `<h2>Notes</h2>` block before `</body>`:

```html
<h2>Notes</h2>
<ul>
  <!-- Pick exactly one of the two forms based on whether vault MCP tools fired this session: -->
  <li><strong>Vault context:</strong> Retrieved ([list of note paths])</li>
  <li><strong>Vault context:</strong> Not retrieved</li>
</ul>
```

If the report already has a notes / references section, use Edit to insert the `<li>` line before its closing `</ul>`.

The gist URL stays out of the HTML body on purpose: each Edit re-fires the auto-publish hook and produces a brand-new gist ID, so any URL embedded in the file becomes stale the instant the next Edit lands. The canonical gist + preview URL is the pair printed to stderr by the step-3 Edit's auto-publish run. Quote that pair to the user when announcing the report.

## Step 4: Decision Extraction

Scan the conversation for decisions, gotchas, or architectural choices that were not already saved via `/remember` or to memory. For each one found, ask the user via `AskUserQuestion`:

> "I noticed this decision: [summary]. Save it to memory?"

Only write decision notes the user confirms. If no unrecorded decisions are found, skip silently.

## Step 5: Session Tidy (Project Scope)

Scope: the current project's session folder only.

1. **List files** in the project's vault session folder via Bash `ls`.
2. **Quick audit** each `.html` file for:
   - **Naming convention:** must match `[N]. [Title].html`
   - **Frontmatter completeness:** HTML comment block at top of `<body>` contains `type`, `project`, `session`, `date`, `status`, `blocked`, `vault_context_retrieved`, `tags`
   - **Status coherence:** `status: completed` with `blocked: true` is contradictory. `status: in-progress` or `status: blocked` on sessions older than 7 days is stale.
3. **Auto-fix minor issues** via Edit:
   - Missing frontmatter fields that can be inferred (e.g., `blocked: false` when status is `completed`; `vault_context_retrieved: false` when the field is absent, since the field defaults to false in pre-existing sessions)
   - `type` field set to a wrong value (correct to `session-report`)

   Each Edit on a marked HTML file re-fires doc-gist's auto-publish hook and produces a fresh gist + preview URL pair on stderr — the prior gist URL becomes orphaned. Surface a `Session [N] republished — new preview: <url>` line per Edit so the user can update any prior shares.
4. **Report issues that need user input:**
   - Files with wrong naming convention (propose new name)
   - Stale statuses (propose update to `completed` or ask)
   - Contradictory status/blocked combos

   If no issues are found, skip silently. Do not report "all clean."
5. **Rollup check:** if the project has 5+ sessions and no `Summary.html` or `Summary.md`, mention it:
   > "This project has [N] sessions and no summary. Run `/session-tidy` for a full rollup."

## Step 6: Finalize

Copy a `/rename` command to the user's clipboard via PowerShell:

```
pwsh -NoProfile -Command "Set-Clipboard '/rename [Project] - [Primary Outcome]'"
```

Then tell the user:

> "Copied `/rename [Project] - [Primary Outcome]` to your clipboard. Paste it to rename this session."

The primary outcome comes from the session title resolved in step 1.

---

## Run-and-report checklist

- [ ] Backend detected and announced
- [ ] Session number resolved from `[N]. *.html` and `[N]. *.md` files (both parsed to preserve sequence across the format migration)
- [ ] HTML composed via doc-gist's shape principles (gallery-anchored)
- [ ] `<!-- @publish-as-gist -->` marker present somewhere in the HTML
- [ ] Frontmatter HTML comment present at top of `<body>`
- [ ] Opening section answers "what shipped / why / impact" for a cold reader
- [ ] Self-contained HTML (inline styles, no external refs)
- [ ] Auto-publish URLs captured from step 2 and step 3 (or HTML emitted to chat when step 2 Write failed)
- [ ] Vault-context line appended via Edit (step 3); step-3 publish's URL pair quoted to the user
- [ ] Decision extraction surfaced any unrecorded items
- [ ] Session tidy reported anomalies or stayed silent
- [ ] `/rename` command copied to clipboard via `pwsh Set-Clipboard`

## Folder map

- `SKILL.md` — this hub. Single-file skill; no companions.
