"""Configuration constants for the fix-push gate hook and its Stop verifier.

Shared between ``fix_push_gate_blocker.py`` (PreToolUse writer) and
``fix_push_gate_stop_verifier.py`` (Stop reader) so both compute an identical
gate-result filename and resolve the same gate script.
"""

import re

BASH_TOOL_NAME: str = "Bash"

ALL_GATED_MCP_WRITE_TOOLS: tuple[str, ...] = (
    "mcp__plugin_github_github__push_files",
    "mcp__plugin_github_github__create_or_update_file",
    "mcp__plugin_github_github__delete_file",
    "mcp__plugin_github_github__merge_pull_request",
)

GIT_PUSH_COMMAND_PATTERN: re.Pattern[str] = re.compile(r"\bgit\b(?:\s+-C\s+\S+)?\s+push\b")

ALL_GIT_SHOW_TOPLEVEL_COMMAND: tuple[str, ...] = ("git", "rev-parse", "--show-toplevel")

ALL_GIT_HEAD_SHA_COMMAND: tuple[str, ...] = ("git", "rev-parse", "HEAD")

ALL_GH_PR_VIEW_IDENTITY_COMMAND: tuple[str, ...] = (
    "gh",
    "pr",
    "view",
    "--json",
    "number,baseRefName",
)

GATE_RESULT_FILENAME_TEMPLATE: str = ".bugteam-pr{number}.gate.json"

CODE_RULES_GATE_INSTALLED_RELATIVE_PATH: str = (
    ".claude/_shared/pr-loop/scripts/code_rules_gate.py"
)

GATE_BASE_REF_TEMPLATE: str = "origin/{base_ref}"

LOOP_STATE_FILENAME: str = "pr-converge-state.json"

LOOP_OUTCOMES_GLOB: str = ".bugteam-pr*-loop*.outcomes.xml"

GATE_EXIT_CLEAN: int = 0
GATE_EXIT_BLOCKING: int = 1
GATE_EXIT_SETUP_ERROR: int = 2

DENY_REASON_TEMPLATE: str = (
    "BLOCKED [fix-push-gate]: code_rules_gate reported a blocking CODE_RULES "
    "violation on lines this push adds. Fix the flagged lines — sweeping the "
    "whole enumerable class per fix-protocol.md Category-K carve-out — and push "
    "again. A fix-induced violation must be resolved in the same loop that "
    "introduced it.\n\n{gate_output}"
)

STOP_BLOCK_REASON_TEMPLATE: str = (
    "BLOCKED [fix-push-gate]: the current HEAD {head_sha} on this PR branch is "
    "not recorded as passing code_rules_gate, and a re-run of the gate against "
    "origin/{base_ref} reports a blocking violation. A fix push bypassed the "
    "deterministic gate. Resolve the flagged lines, re-run the gate to record a "
    "passing result, then end the turn.\n\n{gate_output}"
)
