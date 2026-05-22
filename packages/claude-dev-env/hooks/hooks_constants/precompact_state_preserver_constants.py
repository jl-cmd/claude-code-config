"""Constants for the ``precompact_state_preserver`` PreCompact hook.

Centralizes the registry of known stateful-skill state-file locations, the
field names the hook extracts from each state file, the drop-list of compaction
chaff, and the envelope strings used to render the focus directive. Every
literal the hook emits to stdout (which Claude Code appends to the compactor's
custom_instructions per the PreCompact spec) lives here so the directive shape
stays auditable.

Sources:
    - https://code.claude.com/docs/en/hooks (PreCompact event spec)
    - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
    - https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
"""

from __future__ import annotations

from typing import Final

HOOK_EVENT_NAME_PRECOMPACT: Final[str] = "PreCompact"
TRIGGER_MANUAL: Final[str] = "manual"
TRIGGER_AUTO: Final[str] = "auto"

CLAUDE_JOB_DIR_ENV_VAR: Final[str] = "CLAUDE_JOB_DIR"
PROJECT_STATE_DIRECTORY_FRAGMENT: Final[str] = ".claude/state"

STATE_FILE_FIELD_CURRENT_HEAD: Final[str] = "current_head"
STATE_FILE_FIELD_PHASE: Final[str] = "phase"
STATE_FILE_FIELD_TICK_COUNT: Final[str] = "tick_count"
STATE_FILE_FIELD_WORKTREE: Final[str] = "worktree"
STATE_FILE_FIELD_OPERATOR_FOLLOWUPS: Final[str] = "operator_followups"
STATE_FILE_FIELD_SKILL_NAME: Final[str] = "skill"

PRESERVE_FIELDS_ORDERED: Final[tuple[str, ...]] = (
    STATE_FILE_FIELD_SKILL_NAME,
    STATE_FILE_FIELD_PHASE,
    STATE_FILE_FIELD_CURRENT_HEAD,
    STATE_FILE_FIELD_TICK_COUNT,
    STATE_FILE_FIELD_WORKTREE,
    STATE_FILE_FIELD_OPERATOR_FOLLOWUPS,
)

DIRECTIVE_HEADER: Final[str] = (
    "[precompact-state-preserver] A stateful skill is in flight. "
    "Preserve the load-bearing pointers below and drop the verbose chaff."
)

DIRECTIVE_PRESERVE_HEADING: Final[str] = "MUST PRESERVE (load-bearing pointers):"
DIRECTIVE_DROP_HEADING: Final[str] = "CAN DROP (verbose chaff that re-derives from pointers):"
DIRECTIVE_RESUMPTION_HEADING: Final[str] = "RESUMPTION HINT:"

DROP_LIST_LINES: Final[tuple[str, ...]] = (
    "Per-finding bodies from bugbot/bugteam/copilot reviews — keep counts and IDs only.",
    "Intermediate commit SHAs that are not current_head and are not clean-at markers.",
    "GitHub thread IDs, review IDs, and comment IDs already resolved or replied to.",
    'Per-tick narration prose ("on tick N I did X, then Y") — keep the latest phase only.',
    "Raw tool-call outputs and JSON payloads already summarized into state fields.",
    "Repeated reproductions of file contents Claude can re-read from current_head.",
)

MAX_OPERATOR_FOLLOWUPS_RENDERED: Final[int] = 5
MAX_STATE_FILE_BYTES: Final[int] = 256_000
MAX_DIRECTIVE_TOKENS_APPROX: Final[int] = 500

PR_CONVERGE_STATE_FILENAME: Final[str] = "pr-converge-state.json"
BUGTEAM_STATE_FILENAME: Final[str] = "bugteam-state.json"
LOOP_STATE_FILENAME: Final[str] = "loop-state.json"

JOB_DIR_STATE_FILENAMES: Final[tuple[str, ...]] = (
    PR_CONVERGE_STATE_FILENAME,
    BUGTEAM_STATE_FILENAME,
    LOOP_STATE_FILENAME,
)

PROJECT_STATE_GLOB_PATTERN: Final[str] = "*.json"
