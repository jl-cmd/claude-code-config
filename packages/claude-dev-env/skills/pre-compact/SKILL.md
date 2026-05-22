---
name: pre-compact
description: >-
  Composes a focus directive for `/compact [instructions]` and copies the full
  `/compact <directive>` string to the operator's clipboard so the next prompt
  is a single paste. The directive pins the session's load-bearing identifiers
  (branch, PR, HEAD, worktree, in-flight work, decisions, blockers, files in
  play, follow-ups) and lists the redundant tool outputs the summarizer should
  drop. Use when the user says `/pre-compact`, asks to prep for compaction, or
  asks to compose a focus directive for `/compact`.
disable-model-invocation: true
---

# Pre-Compact

`/compact [instructions]` accepts a focus directive that steers the
compaction-summary LLM toward high-signal content. This skill writes that
directive from the live session and copies the full `/compact <directive>`
string to the operator's clipboard.

**Announce at start:** "I'm composing your compact focus directive."

## Step 1 — Read the live session

Pull the load-bearing identifiers from the current conversation. Run
`git status`, `git rev-parse --short HEAD`, or `gh pr view` when values are
not already in context.

| Field | What to capture | Source |
|---|---|---|
| `branch` | Active branch name | `git branch --show-current` |
| `pr` | Active PR number, when one exists | `gh pr view --json number` |
| `head` | First 7 chars of HEAD SHA | `git rev-parse --short HEAD` |
| `worktree` | Absolute path to the working directory | `pwd` |
| `in_flight` | One sentence describing what is being worked on right now | conversation |
| `decisions` | Architectural choices, library picks, tradeoffs settled this session | conversation |
| `blockers` | Failures observed, root causes identified, fixes pending | conversation |
| `files` | Paths the operator is iterating on (edited or read more than once) | conversation |
| `follow_ups` | What the user asked to be remembered or revisited | conversation |

A field whose value cannot be stated as a concrete identifier is omitted
from the directive.

## Step 2 — Render the directive

Render this exact shape, populating only the fields with concrete values:

```
Preserve:
- Branch: <name> | PR: #<number> | HEAD: <sha7>
- Worktree: <path>
- In-flight: <one sentence>
- Decisions: <bullet per decision>
- Blockers: <bullet per blocker>
- Files: <path>, <path>, <path>
- Follow-ups: <bullet per follow-up>

Drop:
- Tool outputs already applied to files
- Per-tick progress narration
- Resolved findings and superseded SHAs
- Listing/grep output whose conclusion appears above
```

The `Preserve:` block leads so the summarizer maximizes recall first. The
`Drop:` block lists the lightest-touch removals — raw tool outputs are the
safest content to drop because the work they produced lives in the files
and commits.

Source: [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
— "start by maximizing recall to ensure your compaction prompt captures
every relevant piece of information from the trace, then iterate to improve
precision by eliminating superfluous content."

## Step 3 — Copy `/compact <directive>` to the clipboard

Combine `/compact ` with the directive body, then pipe to PowerShell
`Set-Clipboard` via a literal here-string:

```
pwsh -NoProfile -Command "@'
/compact <directive body>
'@ | Set-Clipboard"
```

The `@'…'@` here-string passes the directive verbatim — single quotes,
backticks, and `$` survive intact. The closing `'@` sits at column 0 with
no leading whitespace.

## Step 4 — Hand off

Output exactly:

> Copied `/compact …` to your clipboard. Paste it as your next prompt to
> compact this conversation with focus.

Show the first three `Preserve:` bullets and the first `Drop:` bullet
inline so the operator can spot-check before pasting.

---

## References

- `/compact [instructions]` — [Claude Code commands](https://code.claude.com/docs/en/commands)
- Compaction strategy — [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | This hub — the entire skill. |

## Folder map

- `SKILL.md` — hub. No companions.
