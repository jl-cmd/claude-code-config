"""Constants for the hook-log extractor and init scripts.

Centralizes all named values used by ``hook_log_extractor.py`` and
``hook_log_init.py`` so that production modules carry zero magic values.
"""

from __future__ import annotations

COMMAND_EXCERPT_MAX_CHARACTERS: int = 300
STDOUT_EXCERPT_MAX_CHARACTERS: int = 500
STDERR_EXCERPT_MAX_CHARACTERS: int = 500

INSERT_BATCH_SIZE: int = 500
CONNECT_TIMEOUT_SECONDS: int = 5
OFFLINE_FALLBACK_WALLCLOCK_BUDGET_SECONDS: int = 10

OFFSET_STATE_FILE: str = "C:/Users/jon/.claude/logs/hooks/.state/offsets.json"
OFFLINE_WARNING_LOG: str = "C:/Users/jon/.claude/logs/hook-extractor.log"
PROJECTS_TRANSCRIPT_ROOT: str = "C:/Users/jon/.claude/projects"

NEON_DATABASE_URL_ENVIRONMENT_VARIABLE: str = "NEON_HOOK_LOGS_DATABASE_URL"
BWS_ACCESS_TOKEN_ENVIRONMENT_VARIABLE: str = "BWS_ACCESS_TOKEN"

ATTACHMENT_TYPE_PREFIX: str = "hook_"
TOP_LEVEL_ATTACHMENT_TYPE: str = "attachment"

ATTACHMENT_TYPE_HOOK_SUCCESS: str = "hook_success"
ATTACHMENT_TYPE_HOOK_BLOCKING_ERROR: str = "hook_blocking_error"
ATTACHMENT_TYPE_HOOK_SYSTEM_MESSAGE: str = "hook_system_message"
ATTACHMENT_TYPE_HOOK_ADDITIONAL_CONTEXT: str = "hook_additional_context"

OUTCOME_SUCCESS: str = "success"
OUTCOME_BLOCKED: str = "blocked"
OUTCOME_SYSTEM_MESSAGE: str = "system_message"
OUTCOME_ADDED_CONTEXT: str = "added_context"
OUTCOME_INIT_PROBE: str = "init_probe"

OUTCOME_BY_ATTACHMENT_TYPE: dict[str, str] = {
    ATTACHMENT_TYPE_HOOK_SUCCESS: OUTCOME_SUCCESS,
    ATTACHMENT_TYPE_HOOK_BLOCKING_ERROR: OUTCOME_BLOCKED,
    ATTACHMENT_TYPE_HOOK_SYSTEM_MESSAGE: OUTCOME_SYSTEM_MESSAGE,
    ATTACHMENT_TYPE_HOOK_ADDITIONAL_CONTEXT: OUTCOME_ADDED_CONTEXT,
}

HOOK_CATEGORY_UNCATEGORIZED: str = "uncategorized"

KNOWN_HOOK_CATEGORIES: frozenset[str] = frozenset(
    {
        "advisory",
        "blocking",
        "config",
        "context",
        "diagnostic",
        "git-hooks",
        "github-action",
        "lifecycle",
        "notification",
        "session",
        "system",
        "validation",
        "validators",
        "workflow",
        "worktree",
    },
)

HOOKS_PARENT_DIRECTORY_SEGMENT: str = "hooks"

HOOK_NAME_TOOL_SEPARATOR: str = ":"

SCHEMA_RELATIVE_PATH: str = "schema.sql"
QUERIES_DIRECTORY_NAME: str = "queries"
SQL_FILE_EXTENSION: str = ".sql"

DEFAULT_QUERY_FOR_SUMMARY: str = "top_blockers_since_last_run"

JSONL_FILE_GLOB: str = "*.jsonl"

FLAG_INCREMENTAL: str = "--incremental"
FLAG_FULL_REBUILD: str = "--full-rebuild"
FLAG_SUMMARY: str = "--summary"
FLAG_QUERY: str = "--query"

EXIT_CODE_SUCCESS: int = 0
EXIT_CODE_ENVIRONMENT_MISSING: int = 1

SENTINEL_SESSION_ID: str = "__init_probe_session__"
SENTINEL_HOOK_EVENT: str = "InitProbe"
SENTINEL_HOOK_NAME: str = "init_probe"
SENTINEL_SOURCE_PATH: str = "__init_probe__"
SENTINEL_SOURCE_LINE_NUMBER: int = 0

SUMMARY_COLUMN_HEADINGS: tuple[str, str, str, str] = (
    "hook_name",
    "hook_category",
    "block_count_since_last_run",
    "top_blocked_command_preview",
)

SUMMARY_NO_NEW_BLOCKS_MESSAGE: str = "No new blocks since last run."

TOP_BLOCKED_COMMAND_PREVIEW_MAX_CHARACTERS: int = 80
