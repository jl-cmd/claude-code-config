"""Configuration constants for the autoconverge_cap_terminology_blocker hook.

The autoconverge skill names the Copilot review-poll limit "configured cap" in
every surface. These patterns flag the inconsistent spellings ("poll cap" and a
bare "after the cap") so a doc write keeps one term for that limit.
"""

from re import IGNORECASE, Pattern, compile

ALL_CAP_TERMINOLOGY_PATTERNS: list[Pattern[str]] = [
    compile(r"\bpoll cap\b", IGNORECASE),
    compile(r"\bafter the cap\b", IGNORECASE),
]

CODE_FENCE_PATTERN: Pattern[str] = compile(r"```[\s\S]*?```")
INLINE_CODE_PATTERN: Pattern[str] = compile(r"``[^`]+``|`[^`]+`")

ALL_MARKDOWN_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".mdx", ".markdown", ".rmd"}
)

AUTOCONVERGE_SKILL_PATH_MARKER: str = "skills/autoconverge/"

ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES: frozenset[str] = frozenset(
    {"Write", "Edit", "MultiEdit"}
)

DENY_SYSTEM_MESSAGE: str = (
    "Agent used inconsistent cap terminology in an autoconverge doc — "
    "use 'configured cap'"
)

DENY_ADDITIONAL_CONTEXT: str = (
    "The autoconverge skill names the Copilot review-poll limit "
    "'configured cap'. Rewrite the flagged phrase to 'configured cap' "
    "(for example 'after the configured cap') so every autoconverge surface "
    "reads the same term."
)
