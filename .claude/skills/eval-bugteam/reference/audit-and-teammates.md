# Audit and Teammates

## Subagent Design

The audit function uses a single opus subagent per loop. The subagent is
spawned fresh each loop for clean-room isolation — no state is carried
between audit invocations.

**Key decisions:**

- **Single opus auditor** — one powerful model produces the complete
  audit in a single pass. This avoids the complexity of merging multiple
  partial audits while still benefiting from opus-level reasoning.

- **Fresh spawn per loop** — eliminates bias from prior loop findings.
  Each audit starts from first principles against the current diff.

- **Background execution** — the lead spawns via
  `Agent(run_in_background=true)` and awaits completion notification.

## Output Flow

1. Auditor writes `.bugteam-pr<N>-loop<L>.outcomes.xml` to the worktree
2. Lead reads XML and populates `loop_comment_index`
3. Lead does lead-side triage before spawning FIX

## Teammate Lifecycle

- Spawned at AUDIT action
- Returns on completion (or 120s timeout → hard blocker)
- Lead reads XML output synchronously after completion
