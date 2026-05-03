You are running the pr-converge loop for `jl-cmd/claude-code-config`. Read the full skill spec before starting:

```
C:\Users\jon\.claude\skills\pr-converge\SKILL.md
C:\Users\jon\.claude\skills\pr-converge\workflows\ahk-auto-continue-loop.md
```

**This session has no `ScheduleWakeup`.** Use the AHK auto-continue pacing path from `ahk-auto-continue-loop.md` — the AHK script is already installed at `C:\Users\jon\.claude\skills\pr-converge\scripts\cursor-agents-continue.ahk`. Before your first tick, run the one-time AHK setup from that file:

```
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\Users\jon\.claude\skills\pr-converge\scripts\caller-window-pid.ps1"
```

Capture the printed PID, verify it points at this Cursor window, then launch the auto-typer:

```
"C:\Users\jon\.claude\skills\pr-converge\scripts\cursor-agents-continue.cmd" <PID> --start-on
```

**End every assistant response with:** `Awaiting next "continue" tick.`

---

## Step 0: Assemble the work queue

Run all four commands before touching any PR. They give you the complete picture.

**1. All open PRs — branch, HEAD SHA, mergeable status:**

```bash
gh api 'repos/jl-cmd/claude-code-config/pulls?state=open&per_page=100' --paginate --slurp \
  | jq '[.[][] | {number, title, headRefName, head_sha: .head.sha, mergeable, isDraft}] | sort_by(.number)'
```

**2. Latest bugbot review for each PR number `<N>` from step 1:**

```bash
python "C:\Users\jon\.claude\skills\pr-converge\scripts\fetch_bugbot_reviews.py" \
  --owner jl-cmd --repo claude-code-config --number <N>
```

`classification: "clean"` on the most recent entry means bugbot approved this HEAD.
`classification: "dirty"` means findings remain.
Empty array means bugbot has not reviewed yet — trigger it.

**3. Inline findings for any dirty PR (per dirty `<N>` at its `<HEAD_SHA>`):**

```bash
python "C:\Users\jon\.claude\skills\pr-converge\scripts\fetch_bugbot_inline_comments.py" \
  --owner jl-cmd --repo claude-code-config --number <N> --commit <HEAD_SHA>
```

Each returned object has `path`, `line`, and `body` — the exact location and description of the finding to fix.

**4. Prior bugteam review for each PR (to know which already passed the in-house audit):**

```bash
gh api 'repos/jl-cmd/claude-code-config/pulls/<N>/reviews?per_page=100' --paginate --slurp \
  | jq '[.[][] | select(.body | startswith("## /bugteam"))] | sort_by(.submitted_at) | last | {commit_id, body}'
```

A body ending with `-> clean` at the current HEAD SHA means bugteam already passed for this HEAD.

**Build the work queue from these four inputs:**

| Condition | Action |
|-----------|--------|
| `mergeable: "CONFLICTING"` | Rebase onto main first, then re-check everything |
| `mergeable: "MERGEABLE"` + bugbot dirty | Read inline findings, apply fixes, push, re-trigger bugbot |
| `mergeable: "MERGEABLE"` + bugbot clean + no bugteam clean at this HEAD | Run `/bugteam` |
| `mergeable: "MERGEABLE"` + bugbot clean at HEAD + bugteam clean at same HEAD | `gh pr ready` — converged |

Process PRs in ascending number order within each tier. PRs that modify the same file must merge sequentially — confirm the prior one merged before starting the next.

---

## Scripts to use

All `gh` wrapper scripts live at `C:\Users\jon\.claude\skills\pr-converge\scripts\`. Use `trigger_bugbot.py`, `fetch_bugbot_reviews.py`, `fetch_bugbot_inline_comments.py`, and `mark_pr_ready.py` per the README there. Fix-protocol production edits use `Task` with `subagent_type: "generalPurpose"` plus a Read preamble loading `C:\Users\jon\.claude\agents\clean-coder.md`.
