"""Zoekt MCP usage and repo-to-disk path mapping for PreToolUse permissionDecisionReason."""


def get_zoekt_redirect_message() -> str:
    return (
        "Use Zoekt MCP instead: mcp__zoekt__search(query=\"your pattern\"). "
        "Supports regex, 'file:pattern' for file filtering, 'lang:py' for language. "
        "Also available: mcp__zoekt__search_symbols, mcp__zoekt__find_references, mcp__zoekt__file_content. "
        "Example: mcp__zoekt__search(query=\"verify_theme_assets file:\\.py$\")\n\n"
        "INDEX ROOTS (when Grep/Search in a tree is redirected): set ZOEKT_REDIRECT_INDEXED_ROOTS to a JSON array "
        "of absolute paths, or ~/.claude/zoekt-indexed-roots.json as {\"roots\": [\"Y:/your/repo/\", ...]}. "
        "Optional ZOEKT_REDIRECT_INDEXED_ROOTS_FILE points to a different JSON file. "
        "WSL /mnt/<drive>/... prefixes are derived from Windows roots automatically.\n\n"
        "ZOEKT REPO -> FILESYSTEM PATH MAPPING (for editing files found via Zoekt):\n"
        "  Python           -> Y:/Information Technology/Scripts/Automation/Python/\n"
        "  CDP Automations  -> Y:/Information Technology/Scripts/Automation/Python/CDP Automations/\n"
        "  Behavioral App   -> Y:/Craft a Tale/Behavioral App/\n"
        "  llm-settings       -> C:/Users/jon/.claude/\n"
        "Example: Zoekt returns 'Python - shared_utils/foo.py' -> edit 'Y:/Information Technology/Scripts/Automation/Python/shared_utils/foo.py'"
    )


def get_zoekt_redirect_guidance() -> str:
    return get_zoekt_redirect_message()
