# Registry Extension

How to add a new state-file location to the hook's scan registry.

## The registry

The hook scans two roots:

1. **`$CLAUDE_JOB_DIR`** — only the filenames listed in
   `JOB_DIR_STATE_FILENAMES` are checked.
2. **`<cwd>/.claude/state/`** — every `*.json` is scanned, no registry
   edit required.

Anything that fits into the `<cwd>/.claude/state/*.json` location works
out of the box. The registry edit below applies only to the `$CLAUDE_JOB_DIR`
slot, where the hook needs to know the exact filename.

## Adding a `$CLAUDE_JOB_DIR` filename

Edit `packages/claude-dev-env/hooks/hooks_constants/precompact_state_preserver_constants.py`:

```python
NEW_SKILL_STATE_FILENAME: Final[str] = "<your-skill>-state.json"

JOB_DIR_STATE_FILENAMES: Final[tuple[str, ...]] = (
    PR_CONVERGE_STATE_FILENAME,
    BUGTEAM_STATE_FILENAME,
    LOOP_STATE_FILENAME,
    NEW_SKILL_STATE_FILENAME,
)
```

That is the entire change. The hook iterates `JOB_DIR_STATE_FILENAMES` in
order, so the new filename is picked up on the next PreCompact event.

## Tests

Add one round-trip test alongside the existing seven in
`packages/claude-dev-env/hooks/lifecycle/test_precompact_state_preserver.py`:

```python
def test_new_skill_state_is_discovered_in_job_dir(tmp_path: Path) -> None:
    state_path = _write_state_file(
        tmp_path / "job",
        "<your-skill>-state.json",
        {"skill": "<your-skill>", "phase": "...", "current_head": "..."},
    )
    hook_run = _run_hook(
        _precompact_payload(cwd=str(tmp_path)),
        extra_env={"CLAUDE_JOB_DIR": str(tmp_path / "job")},
    )
    assert hook_run.returncode == 0
    assert state_path.as_posix() in hook_run.stdout
    assert "skill: <your-skill>" in hook_run.stdout
```

## When NOT to extend the registry

Skip the registry edit and use the project-local fallback when:

- The skill writes its state file inside a project checkout that has a
  `.claude/state/` directory.
- Multiple sibling state files might exist simultaneously and the order
  of preference is naturally lexicographic (filenames sort to the same
  order the scan finds them in).
- You want zero coupling between the skill and the hook's constants
  module.

The job-dir slot is for skills that explicitly run detached from any
project checkout (background jobs, scheduled agents) and need a stable
filename the hook can find.

## First-match-wins ordering

The hook returns the first state file that exists AND parses cleanly AND
is under the 256 KB cap. When two state files would both match, the one
listed earlier in `JOB_DIR_STATE_FILENAMES` wins. Project-local
`.claude/state/*.json` is always scanned after every entry in
`JOB_DIR_STATE_FILENAMES`, so adding a job-dir filename gives it
priority over project-local files.
