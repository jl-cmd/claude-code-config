#!/usr/bin/env python3
"""Path-aware Zoekt search redirector.

Blocks Grep/Search tool calls ONLY when targeting a directory inside a
Zoekt-indexed repo.  Allows searches outside indexed repos, searches
targeting a specific file, and Bash grep/rg commands (which are already
denied by settings.json deny list).

Indexed repos and their filesystem paths are listed in INDEXED_PATHS.
"""
import json
import os
import re
import sys
from typing import Final

CONTENT_SEARCH_TOOLS = {"Grep", "Search"}

BASH_CONTENT_SEARCH_PATTERNS = [
    (re.compile(r"^\s*grep\s", re.IGNORECASE), "grep"),
    (re.compile(r"^\s*grep$", re.IGNORECASE), "grep"),
    (re.compile(r"\|\s*grep\s", re.IGNORECASE), "piped grep"),
    (re.compile(r"\|\s*grep$", re.IGNORECASE), "piped grep"),
    (re.compile(r"^\s*rg\s", re.IGNORECASE), "ripgrep"),
    (re.compile(r"^\s*rg$", re.IGNORECASE), "ripgrep"),
    (re.compile(r"\|\s*rg\s", re.IGNORECASE), "piped ripgrep"),
    (re.compile(r"^\s*findstr\s", re.IGNORECASE), "findstr"),
    (re.compile(r"^\s*Select-String", re.IGNORECASE), "PowerShell Select-String"),
    (re.compile(r"^\s*sls\s", re.IGNORECASE), "PowerShell sls"),
    (re.compile(r"^\s*ack\s", re.IGNORECASE), "ack"),
    (re.compile(r"^\s*ag\s", re.IGNORECASE), "silver searcher"),
    (re.compile(r"^\s*git\s+grep\s", re.IGNORECASE), "git grep"),
]

# Paths that Zoekt indexes (Windows format, lowercase, forward slashes).
# Order: most specific first so CDP Automations matches before Python.
INDEXED_PATHS = [
    "y:/information technology/scripts/automation/python/cdp automations/",
    "y:/information technology/scripts/automation/python/",
    "c:/users/jon/.claude/",
    "y:/craft a tale/behavioral app/",
]

# WSL equivalents (same order).
INDEXED_PATHS_WSL = [
    "/mnt/y/information technology/scripts/automation/python/cdp automations/",
    "/mnt/y/information technology/scripts/automation/python/",
    "/mnt/c/users/jon/.claude/",
    "/mnt/y/craft a tale/behavioral app/",
]

ZOEKT_REDIRECT_MESSAGE = (
    "Use Zoekt MCP instead: mcp__zoekt__search(query=\"your pattern\"). "
    "Supports regex, 'file:pattern' for file filtering, 'lang:py' for language. "
    "Also available: mcp__zoekt__search_symbols, mcp__zoekt__find_references, mcp__zoekt__file_content. "
    "Example: mcp__zoekt__search(query=\"verify_theme_assets file:\\.py$\")\n\n"
    "ZOEKT REPO -> FILESYSTEM PATH MAPPING (for editing files found via Zoekt):\n"
    "  Python           -> Y:/Information Technology/Scripts/Automation/Python/\n"
    "  CDP Automations  -> Y:/Information Technology/Scripts/Automation/Python/CDP Automations/\n"
    "  Behavioral App   -> Y:/Craft a Tale/Behavioral App/\n"
    "  llm-settings       -> C:/Users/jon/.claude/\n"
    "Example: Zoekt returns 'Python - shared_utils/foo.py' -> edit 'Y:/Information Technology/Scripts/Automation/Python/shared_utils/foo.py'"
)

ZOEKT_REDIRECT_GUIDANCE: Final[str] = ZOEKT_REDIRECT_MESSAGE
DESTRUCTIVE_GATE_LABEL_PREFIX: Final[str] = "[destructive-gate]"

# Common file extensions — if the path ends with one, it's a specific file.
_FILE_EXT_RE = re.compile(r"\.\w{1,10}$")


def _normalize(path: str) -> str:
    """Lowercase, forward slashes, trailing slash for dirs."""
    return path.replace("\\", "/").lower()


def _is_specific_file(path: str) -> bool:
    """True if path looks like a single file (has a file extension)."""
    return bool(_FILE_EXT_RE.search(path))


def _is_in_indexed_repo(path: str) -> bool:
    """True if the normalized path is inside any Zoekt-indexed repo."""
    norm = _normalize(path)
    if not norm.endswith("/"):
        norm += "/"
    for prefix in INDEXED_PATHS:
        if norm.startswith(prefix):
            return True
    for prefix in INDEXED_PATHS_WSL:
        if norm.startswith(prefix):
            return True
    return False


def build_block_payload(brief_label: str, full_reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
        },
        "decision": "block",
        "reason": full_reason,
        "systemMessage": f"{DESTRUCTIVE_GATE_LABEL_PREFIX} {brief_label}",
        "suppressOutput": True,
    }


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    block_reason = None

    if tool_name in CONTENT_SEARCH_TOOLS:
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", "")

        # No path provided — use CWD
        if not path:
            path = os.getcwd()

        # Allow searches targeting a specific file
        if _is_specific_file(path):
            sys.exit(0)

        # Only block if the target directory is inside an indexed repo
        if _is_in_indexed_repo(path):
            block_reason = f"{tool_name}(pattern: \"{pattern}\", path: \"{path}\")"

    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        for regex, command_name in BASH_CONTENT_SEARCH_PATTERNS:
            if regex.search(command):
                block_reason = f"Bash({command_name})"
                break

    if block_reason:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"BLOCKED: {block_reason}. {ZOEKT_REDIRECT_MESSAGE}",
            }
        }
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
