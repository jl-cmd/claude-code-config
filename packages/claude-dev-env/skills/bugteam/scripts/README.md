# Bugteam utility scripts

Scripts in this directory are **executed** by the lead or teammates. They are not loaded into context as instructions (see Anthropic [Skill authoring best practices — Progressive disclosure](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#progressive-disclosure-patterns)).

| Script | Purpose |
|--------|---------|
| `bugteam_preflight.py` | Run pytest (when configured) and optional `pre-commit` before `/bugteam`. |

## `bugteam_preflight.py`

From the repository root:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_preflight.py"
```

- Skips pytest when `BUGTEAM_PREFLIGHT_SKIP=1`.
- Skips pytest when `pytest.ini` / `pyproject.toml` exists but no `test_*.py` / `*_test.py` files are found under the repo root.
- Pytest exit code `5` (no tests collected) is treated as success.
- Add `--pre-commit` to run `pre-commit run --all-files` when `.pre-commit-config.yaml` exists.
