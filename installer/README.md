# agent-gate-installer

One-command installer for the agent-gate prompt evaluation gate.

## Prerequisites

- Node.js 18+
- Python 3.12+
- `GH_TOKEN` with access to `jl-cmd/agent-gate`

## Usage

Default install:

```bash
npx agent-gate-installer
```

Verbose mode:

```bash
npx agent-gate-installer --verbose
```

Update existing install:

```bash
npx agent-gate-installer --update
```

Uninstall:

```bash
npx agent-gate-installer --uninstall
```

Non-interactive mode:

```bash
npx agent-gate-installer --non-interactive
```

Help:

```bash
npx agent-gate-installer --help
```

## What Gets Installed

The installer performs these steps in order:

1. Validates `GH_TOKEN` (prompting only when interactive mode is allowed)
2. Detects Python 3.12+
3. Clones or updates `jl-cmd/agent-gate` into `~/.claude/agent-gate`
4. Creates a virtual environment at `~/.claude/agent-gate/.venv` (if missing)
5. Installs editable packages:
   - `packages/agent-gate-core`
   - `packages/agent-gate-claude`
   - `packages/agent-gate-prompt-refinement`
   - `agent-gate[dev]`
6. Merges 3 gate hooks into `~/.claude/settings.json`
7. Registers MCP server `agent-gate` in `settings.json`
8. Runs a verification import check

## Install Location

- Repo clone: `~/.claude/agent-gate`
- Virtual environment: `~/.claude/agent-gate/.venv`
- Claude settings: `~/.claude/settings.json`

## Idempotency

Running install multiple times is safe:

- Existing repo clone is pulled instead of recloned.
- Existing venv is reused.
- Existing hook entries are updated in place (not duplicated).
- MCP server entry is replaced in place.
- Unrelated `settings.json` fields are preserved.

## Troubleshooting

- Missing token:
  - Set `GH_TOKEN` before running, or run interactive mode and enter it when prompted.
  - `--non-interactive` exits immediately if `GH_TOKEN` is missing.
- Python errors:
  - Ensure Python 3.12+ is installed and available as `python3`, `python`, or `py -3`.
- Git clone/pull errors:
  - Verify token scope and private repo access.
- `settings.json` parse error:
  - Fix malformed JSON in `~/.claude/settings.json` and rerun.

After install, update, or uninstall, restart Claude Code.
