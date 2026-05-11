# Fix protocol

Single-PR (no `state.json`): production edits run in main session via
`Agent` (`subagent_type: "clean-coder"`). Multi-PR (`state.json`):
clean-coder teammate; orchestrator never edits inline. Hook handling
per [ground-rules.md](ground-rules.md).

**Multi-PR (`state.json`) teammate obligations** (plus TDD, commit, push):

- For each addressed finding, posts a fix reply via
  `add_reply_to_pull_request_comment(owner, repo, pullNumber, commentId, body)`
  (what changed + commit identifier), then resolves the thread via
  `pull_request_review_write(method="resolve_thread", threadId=<node_id>, owner=..., repo=..., pullNumber=...)`.
  Capture each thread's `node_id` from the review comments fetch.
  Posts all replies and resolutions **before** writing `state.json` and going idle.
- Writes `last_action: "fix_pushed"`, `current_head: <new SHA>`,
  `bugbot_clean_at: null`, `bugbot_down: false`, `phase: "BUGBOT"`,
  `status: "awaiting_bugbot"`, `last_updated` (ISO-8601 UTC) to
  `state.json` (per §Concurrency).
- Goes idle. Orchestrator spawns follow-up `general-purpose` agent for
  bugbot trigger and monitoring.

Orchestrator does not reply inline, trigger bugbot, or read repo source
files during fix phase in multi-PR mode.

### Single-PR fix workflow

**Single-PR (no `state.json`) — same gates, main session executor:**

- Read each referenced file:line.
- Write failing test first when finding has behavior to test. Pure doc /
  comment / naming nits with no behavior → straight to fix.
- **Implement** via `Agent` (`subagent_type: "clean-coder"`).
  Full-stop if `Agent` is unavailable.
- Stage affected files and create one new commit on existing branch:
  ```bash
git add <files> && git commit -m "fix(review): <brief summary>"
  ```
**Pre-commit gate:** honor hooks; full-stop on bypass.
- Push the new commit:
  ```bash
git push origin <BRANCH>
  ```
**Pre-push gate:** honor hooks; full-stop on bypass. Capture new HEAD
only after both gates pass; set `current_head`, `bugbot_clean_at = null`.
- For each addressed comment thread, post a fix reply then resolve the thread.
  Capture each thread's `node_id` from the review comments fetch in Step 2.

  Reply inline:
  ```
  add_reply_to_pull_request_comment(owner=OWNER, repo=REPO, pullNumber=NUMBER, commentId=COMMENT_ID, body="Fixed in <SHA> — <what changed>")
  ```

  Then resolve the thread:
  ```
  pull_request_review_write(method="resolve_thread", threadId=<thread_node_id>, owner=OWNER, repo=REPO, pullNumber=NUMBER)
  ```

- Publish a fix summary via `/doc-gist`: concise HTML with commit SHA,
  files changed, one-line per fix, and any findings left unaddressed.
  Post the published URL as a comment via `add_issue_comment`.
- **After pushing a fix, always run Step 3 (`bugbot run`) in the same
  tick** regardless of phase. New commit **resets full convergence cycle**:
  prior bugbot clean and prior bugteam clean on older SHA do **not**
  count toward convergence on new `HEAD`. Must re-obtain bugbot CLEAN on
  `current_head`, then bugteam CLEAN on same `HEAD` with no
  intervening push. Re-triggering in same tick saves a wakeup cycle vs
  deferring Step 3.

**Self-audit checklist — verify every step before scheduling next wakeup:**

- [ ] Read each referenced file:line
- [ ] Wrote failing test (when behavior to test exists)
- [ ] Spawned clean-coder to implement
- [ ] Staged + committed (hook gate: passed; full-stop on bypass)
- [ ] Pushed (pre-push gate: passed; full-stop on bypass)
- [ ] Posted fix reply on each addressed comment thread
- [ ] Resolved each addressed comment thread
- [ ] Published fix summary via /doc-gist, posted URL as comment
- [ ] `bugbot_clean_at = null` set; `current_head` captured
- [ ] Step 3 (bugbot re-trigger) completed
