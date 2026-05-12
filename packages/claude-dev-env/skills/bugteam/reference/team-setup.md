# Run setup and loop state

## Pre-flight (before Step 0)

### Utility scripts

Shell-heavy steps live under
[`_shared/pr-loop/scripts/`](../../_shared/pr-loop/scripts/) (run, do not paste
into context). Utility scripts are **executed**, not loaded as primary context
([`sources.md`](sources.md) § Progressive disclosure and utility scripts).

```bash
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/preflight.py"
```

Non-zero → fix before grant. `BUGTEAM_PREFLIGHT_SKIP=1` emergency only.
`--pre-commit` if `.pre-commit-config.yaml` exists.

**Auto-remediation for `core.hooksPath`:** when preflight fails with stderr
containing `core.hooksPath` (the message starts with `bugteam_preflight:
core.hooksPath is`, or `Git-side CODE_RULES enforcement is not active`), Claude
must auto-invoke the fix script — do not fall through to `AskUserQuestion`, do
not punt to the user, do not ask for confirmation:

```bash
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/fix_hookspath.py"
```

The fix script removes any non-canonical local-scope override on the active
repository, sets the global `core.hooksPath` to `~/.claude/hooks/git-hooks` if
missing or wrong, and re-runs `preflight.py`. Its exit code becomes the
preflight outcome. Exit 0 → continue to Step 0. Non-zero only when the
canonical hooks directory is missing (run `npx claude-dev-env .` first) or
`git config --global` writes are blocked. Other preflight failures (pytest,
pre-commit) still require manual fixes —
the auto-remediation only applies to the `core.hooksPath` failure mode.

## Step 0 — Grant project permissions (detail)

Before spawning any subagents, grant the session write access to the project's `.claude/**` tree:

```bash
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/grant_project_claude_permissions.py"
```

`${CLAUDE_SKILL_DIR}` is a Claude Code host-managed token, pre-substituted by the runtime before any shell sees it. Unlike `${TMPDIR}` and similar shell parameter expansions, it does not depend on the shell’s expansion semantics, so it behaves the same on Unix and Windows shells.

The script reads `Path.cwd()` and writes idempotent allow rules into `~/.claude/settings.json`. Run from the project root. If it fails (non-zero exit), surface the error and stop — do not proceed without the grant.

This is the **first** action of every `/bugteam` invocation, before any subagent spawn. The corresponding revoke runs at Step 5 regardless of how the cycle exits.

## Step 1 — Resolve PR scope (detail)

Same resolution path as `/findbugs`:

1. Call `pull_request_read(method="get", pullNumber=N, owner=O, repo=R)` to fetch PR metadata; capture `number`, `headRefName`, `baseRefName`, and `url` from the response. Falls back to the merge-base diff path when no PR exists.
2. Fall back to `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`.
3. Neither → refuse per refusal cases in `SKILL.md`.

Capture `<owner>/<repo>`, head branch, base branch, PR number, PR URL. This scope persists across every loop — `/bugteam` runs to completion from the single up-front confirmation.

For multi-PR invocations, capture `all_prs = [{number, owner, repo, baseRef, headRef, url}, ...]`. A single-PR invocation produces a one-element list and follows the same downstream rules.

### Per-PR workspace

For each PR in `all_prs`:

1. Create `<run_temp_dir>/pr-<N>/`.
2. Run `git worktree add "<run_temp_dir>/pr-<N>/worktree" origin/<headRef>`.
3. Record the absolute worktree path alongside the PR's other fields.

Background subagents for a PR operate inside that PR's worktree. Step 4 teardown runs `git worktree remove "<run_temp_dir>/pr-<N>/worktree"` for each PR before the shared `rmtree`.

## Step 2 — Run name and temp directory (detail)

### Run specification

- **Run name:** `bugteam-pr-<number>` for single-PR invocations, `bugteam-<sanitized-head-branch>` for multi-PR or no-PR invocations. The name is deterministic so `<run_temp_dir>` and the team task list are re-entrant across sessions.

- **Branch-name sanitization (no-PR fallback only):** Before substituting `<head-branch>` into the `run_name` template, replace every character outside `[A-Za-z0-9._-]` with `-`. The whitelist keeps safe portable filename characters only; OS-reserved and shell-special characters (`/ \ : * ? < > | "` plus ASCII control characters `0x00`–`0x1F`) fall outside the whitelist and become `-`. Example: `feat/foo*bar` → `feat-foo-bar`; `run_name` becomes `bugteam-feat-foo-bar`. Apply sanitization when `run_name` is first assembled so every downstream use (temp dir, cleanup) sees the safe form.

- **Per-run temp directory (resolved once, reused everywhere):** After `run_name` is captured, resolve a portable absolute path: `Path(tempfile.gettempdir()) / run_name` (requires `import tempfile`). `tempfile.gettempdir()` honors `TMPDIR`, `TEMP`, and `TMP` in platform-correct order and falls back to `C:\Users\<user>\AppData\Local\Temp` on Windows or `/tmp` on Unix. Capture the resolved absolute path as `<run_temp_dir>` and pass that literal path to every shell command that follows.

- **Subagent roles (spawned per loop, not at invocation start):**
  - `bugfind` — `code-quality-agent`, model opus (Opus 4.7 at default xhigh effort)
  - `bugfix` — `clean-coder`, model opus (Opus 4.7 at default xhigh effort)

### Loop state block

Loop state (lead; not a single script; per-PR): the variables below are tracked independently for each PR in `all_prs`. Each PR has its own cycle, state, and exit reason.

```bash
loop_count=0
last_action="fresh"
last_findings='{"total": 0}'
audit_log=""
run_temp_dir="<absolute-path>/<run_name>"
starting_sha="$(git -C "<run_temp_dir>/pr-<N>/worktree" rev-parse HEAD)"
loop_comment_index=""
```

The block above mixes lead-internal variables and one shell command (`starting_sha`). Read it as instructions, not a single runnable script.

**`loop_comment_index` scope (per-loop, not cross-loop):** Reset at the start of every AUDIT action, populated as finding comments are posted during AUDIT, consumed by the matching FIX action when it posts fix replies, and discarded after FIX completes. It does not persist across loops; each loop starts with an empty index and its own fresh set of comment URLs.

Each entry: `{loop, finding_id, finding_comment_id, finding_comment_url, used_fallback, fix_status}`. Populated by AUDIT, consumed by FIX.

### Team creation (required)

After `run_temp_dir` is resolved, create the audit team:

```
TeamCreate(team_name="bugteam",
           description="Bugteam audit-fix orchestrator")
```

The team is the master container — all PRs, loops, and teammates run under it.
Per-PR logical grouping uses task subject prefixes and teammate naming (see
below). The team is cleaned up at teardown, only when the PR is fully converged.

#### Multi-PR sub-team tracking

When `/bugteam` runs against multiple PRs across repos, each PR operates as a
logical sub-team within the master `bugteam` team. The PR identity token is
`{owner}/{repo}#{N}` (e.g. `jl-cmd/claude-code-config#422`). In teammate
names and filesystem paths, it is slugified to `{owner}-{repo}-pr-{N}`.

- **Teammate name:** `bugfind-{owner}-{repo}-pr{N}-loop{L}-{letter}`
- **Task subject:** `{owner}/{repo}#{N} audit {letter}`
- **Outcome XML:** `<run_temp_dir>/{owner}-{repo}-pr-{N}/loop-{L}-{letter}.outcomes.xml`

The lead filters by the slugified prefix to group tasks and teammates by PR.
Self-claiming by task subject prefix keeps each teammate on its assigned PR.

### --bugbot-retrigger flag

**`--bugbot-retrigger` flag:** when present, the FIX subagent posts a `bugbot
run` issue comment via the Step 2.5 issue-comments fallback endpoint after
every successful FIX push, to re-trigger Cursor's bugbot on the new commit.
