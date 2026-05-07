"""Configuration constants for the state_description_blocker PreToolUse hook."""

from re import IGNORECASE, Pattern, compile

ALL_COMMENT_TRANSITION_PATTERNS: list[Pattern] = [
    compile(r"instead of", IGNORECASE),
    compile(r"\bpreviously\b", IGNORECASE),
    compile(r"\bnow uses\b", IGNORECASE),
    compile(r"\bnow does\b", IGNORECASE),
    compile(r"\bnow handles\b", IGNORECASE),
    compile(r"\bnow supports\b", IGNORECASE),
    compile(r"\bwas previously\b", IGNORECASE),
    compile(r"\bwere previously\b", IGNORECASE),
    compile(r"\bused to\b", IGNORECASE),
    compile(r"\bno longer\b", IGNORECASE),
    compile(r"\bhas been updated\b", IGNORECASE),
    compile(r"\bhave been updated\b", IGNORECASE),
    compile(r"\bhas been changed\b", IGNORECASE),
    compile(r"\bhave been changed\b", IGNORECASE),
    compile(r"\breplaced by\b", IGNORECASE),
    compile(r"\breplaces\b", IGNORECASE),
    compile(r"\bchanged from\b", IGNORECASE),
    compile(r"\bswitched from\b", IGNORECASE),
    compile(r"\bswitched to\b", IGNORECASE),
    compile(r"\bmigrated from\b", IGNORECASE),
    compile(r"\bmigrated to\b", IGNORECASE),
]

ALL_MARKDOWN_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".mdx", ".markdown", ".rmd"}
)

ALL_COMMENT_BEARING_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".rs",
        ".go",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".scala",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".psm1",
        ".sql",
        ".yaml",
        ".yml",
        ".tf",
        ".json",
        ".css",
        ".scss",
        ".less",
    }
)
