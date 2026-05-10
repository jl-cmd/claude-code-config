---
name: doc-gist
description: Renders Claude-authored markdown (plan, work-in-progress note, decision record, runbook, design doc, any structured writeup) OR a git rebase report (with `--rebase`, comparing ORIG_HEAD vs HEAD with file-by-file diffs and a `git range-diff` walk) into a styled HTML page using an Anthropic-inspired template, uploads the result as a private (secret) GitHub gist via `gh gist create`, and returns an htmlpreview.github.io URL the user can open as a webpage. Trigger on `/doc-gist`, "publish this as a gist", "share my plan as a webpage", "make a gist of this doc", "render these notes to a webpage", "publish this writeup", "share this decision record", "show me the rebase changes as HTML", "rebase report", "what was gained or lost in that rebase", or any request to turn working notes/plans/decisions OR a rebase delta into a shareable styled webpage.
---

# Doc → Gist → Webpage

Take Claude-authored markdown (a plan, decision, status update, runbook, anything) OR a fresh git rebase, render it through a mode-appropriate styled HTML template, upload as a private GitHub gist, and return a clickable webpage URL.

## Modes

- **Doc mode** (default): markdown body via stdin or file. Produces a styled doc with TOC sidebar.
- **Rebase mode** (`--rebase`): collects ORIG_HEAD vs HEAD vs auto-detected base, renders pre-vs-post panels, gained/lost file lists, file-by-file diff hunks (green/orange line tinting), and a `git range-diff` commit walk.

## Gotchas

- **Doc mode** authoring path is **markdown via stdin** (or a non-`.md` file path). The repo's `md_to_html_blocker` hook refuses Write/Edit on `.md` files outside `.claude/`, so do not save the markdown to a `.md` file before running the script — pipe it directly: `$markdown | python publish.py --input -`.
- **Rebase mode** ignores `--input` entirely. It auto-collects from git: pre-rebase tip = `ORIG_HEAD` (override with `--pre`), post-rebase tip = `HEAD` (override with `--post`), base = first match of `@{upstream}` / `origin/main` / `origin/master` / `main` / `master` (override with `--base`). `ORIG_HEAD` is overwritten by the next destructive git op — run rebase mode immediately, or pass `--pre <sha>` recovered from `git reflog`.
- Doc-mode front-matter is optional. Without it, `--title` is required. Front-matter recognises `title:`, `eyebrow:`, `summary:` (one per line, simple `key: value` form, no nesting). Rebase mode ignores front-matter entirely.
- Gist is **secret by default** (`gh gist create` runs without `--public`). Anyone with the URL can view, but it does not appear in search or the user's public profile.
- The htmlpreview URL takes a few seconds to render the first time as the renderer fetches the raw gist content. If the page is blank, refresh once.
- `gh` must be installed and authenticated (`gh auth status`). When `gh gist create failed` appears, run `gh auth login` and retry, or pass `--no-gist`.
- Doc mode's built-in markdown converter handles headings (h1–h4), paragraphs, ordered/unordered lists, bold, italic, inline code, fenced code blocks, blockquotes, links, and horizontal rules. Tables and complex constructs are not parsed — for those, hand-author HTML and pass `--input file.html`.
- Doc-mode TOC sidebar auto-builds from h2/h3 headings. With fewer than two headings, the TOC list is empty and the sidebar shows only the "In this doc" header.
- Doc-mode body text is HTML-escaped through a placeholder protocol — Claude's content in the markdown source cannot inject raw HTML unless the input file is `.html`.
- Rebase mode rejects refs containing whitespace or shell metacharacters (`;`, `|`, `&`, backtick, `$`, `<`, `>`). Recover from `git reflog` if a tag name happens to contain one of these.
- Rebase mode embeds the actual `git diff` patch text per file, with each file expanding into nested **Removals** (clay-themed) and **Additions** (olive-themed) sub-panels. Hunk headers render in GitHub blue, metadata lines (`diff --git`, `index`, `+++`, `---`) in muted gray. Each file is truncated at 400 lines per side.
- File status badges: `lost` (only in pre-rebase changeset), `gained` (only in post-rebase changeset), `ported` (in both, blob hashes at pre tip and post tip are identical — file carried across the rebase byte-for-byte), `modified` (in both, blob hashes differ — rebase reshaped the file). The ported-vs-modified split is content-based, not numstat-based: two patches with the same `+5/−3` totals but different actual lines are correctly flagged `modified`.
- Rebase mode does NOT include generic "typically because…" boilerplate ledes. Each section heading sits directly above its data unless Claude supplies prose specific to the rebase via the `--why-summary`, `--why-gained-lost`, `--why-files`, or `--why-commits` flags. Each flag accepts an HTML string. Flags omitted means no lede paragraph at all.
- Rebase reports open with a three-bucket "story panel" at the top: **What's new**, **What's gone**, **What's kept**. Each bucket is populated from the `--whats-new`, `--whats-gone`, `--whats-kept` flag. Each flag accepts an HTML string. Claude generates per-rebase prose for all three buckets on every invocation. When a bucket is omitted, the panel renders a placeholder ("Not supplied. Pass --whats-new / --whats-gone / --whats-kept.") so missing buckets are visible at a glance.

## When this skill applies

Trigger on any of:

- `/doc-gist`
- "publish this as a gist"
- "share my plan as a webpage"
- "make a gist of this doc"
- "render these notes to a webpage"
- "publish this writeup as a webpage"
- "share this decision record"
- "post my plan"

Refusal cases — first match wins:

- **No content supplied.** Respond exactly: `Provide markdown via stdin or pass --input <path>. Front-matter or --title is required so the H1 is set.`
- **`gh` is not authenticated.** Respond exactly: `Run "gh auth login" and retry, or pass --no-gist to keep the report local.`

## Process

1. **Author the markdown.** Generate the doc body in chat (Claude's working memory). Front-matter is optional: a `title:`/`eyebrow:`/`summary:` block at the top sets metadata.

2. **Pipe through the script.** Markdown lives only on stdin (or a non-`.md` path) — the hook will block any attempt to save it as a `.md` file outside `.claude/`. Use this PowerShell pattern:

   ```powershell
   $markdown = @'
   ---
   title: Plan: ...
   eyebrow: plan · backend
   summary: One-sentence TL;DR.
   ---

   ## Why

   ...
   '@; $markdown | python "C:/Users/jon/.claude/skills/doc-gist/scripts/publish.py" --input -
   ```

   Or pass a file: `python publish.py --input ./plan.html` for hand-authored HTML.

   Pass through any user-specified `--title`, `--eyebrow`, `--summary`, `--repo`, `--output`, `--no-gist`, or `--no-open` flags verbatim.

3. **Report the outcome.** Quote the **Preview** URL (the htmlpreview.github.io link) and the **Gist** URL from stderr to the user as clickable links. The preview URL is what the user opens to see the styled webpage; the gist URL is for editing/deleting.

4. **If the script fails**, surface the exact error. Most failures map directly to a Gotcha entry — check there before guessing.

### Run-and-report checklist

Copy and check off:

- [ ] Front-matter or `--title` provides the H1
- [ ] Markdown delivered via stdin (or HTML via `--input file.html`)
- [ ] Script exited 0
- [ ] Preview URL printed on stdout
- [ ] Both `Gist:` and `Preview:` lines from stderr quoted to the user

## Examples

**A plan, piped via stdin:**

```powershell
$markdown = @'
---
title: Plan: Migrate event log to Postgres
eyebrow: plan · ingestion
summary: Replace the file-tailing log shipper with direct Postgres writes for sub-second visibility on event freshness.
---

## Why

The current shipper batches events on disk for 30 seconds before flushing.
That window hides ingestion failures. Direct writes give us a real-time
freshness signal and remove the disk-buffer failure mode.

## Approach

1. Add a Postgres sink alongside the file shipper
2. Dual-write for one week, compare counts daily
3. Cut over reads
4. Remove the file shipper in a follow-up

## Risks

- **Postgres write amplification.** Bound by batching at the producer side.
- **Schema drift.** Sink owns its own schema; producer holds an event-version field.
'@; $markdown | python "C:/Users/jon/.claude/skills/doc-gist/scripts/publish.py" --input -
```

Stderr (verbatim shape):
```
Wrote C:/Users/.../Temp/doc-gist-abc.html
Gist: https://gist.github.com/<user>/<id>
Preview: https://htmlpreview.github.io/?https://gist.githubusercontent.com/<user>/<id>/raw/doc-gist-abc.html
Opened gist preview in default browser.
```

**A WIP status update with explicit flags:**

```powershell
$markdown | python "C:/Users/jon/.claude/skills/doc-gist/scripts/publish.py" --input - --title "WIP: Auth migration" --eyebrow "wip · backend"
```

**Hand-authored HTML (advanced; tables, custom panels):**

```
python "C:/Users/jon/.claude/skills/doc-gist/scripts/publish.py" --input ./decision.html --title "Decision: Postgres for sessions"
```

**Local-only mode (no upload, no browser):**

```powershell
$markdown | python "C:/Users/jon/.claude/skills/doc-gist/scripts/publish.py" --input - --output "Y:/Projects/foo/plan.html" --no-gist --no-open
```

## Folder map

- `SKILL.md` — this hub.
- `config/` — magic values, gh-command tuples, frontmatter keys, template-replacement binder. Path exempts UPPER_SNAKE constants from the constants-location rule.
- `scripts/` — runtime entry point and inline markdown converter. Run, don't read.
- `templates/` — the HTML template the script fills.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Hub — principle, gotchas, process, examples. |
| `config/__init__.py` | Re-exports `constants` so `from config import constants` resolves statically. |
| `config/constants.py` | gh-command tuples, gist URL builders, frontmatter keys, heading-level constants, `make_template_replacements` binder. |
| `scripts/publish.py` | Runtime entry point. Reads stdin/file, parses front-matter, converts markdown, fills template, writes HTML, uploads as private gist, opens preview URL. |
| `templates/document.html.tmpl` | Page layout, embedded CSS, and `<!-- TPL:KEY -->` markers the script fills. |
