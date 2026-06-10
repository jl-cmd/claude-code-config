"""Constants for the verified-commit gate hook family.

Shared by ``verification_verdict_store.py``, ``verified_commit_gate.py``,
and ``verifier_verdict_minter.py`` so every tunable lives in one place.
"""

from __future__ import annotations

GIT_TIMEOUT_SECONDS = 30
ROOT_KEY_HEX_LENGTH = 16
VERDICT_JSON_INDENT = 2
CLAUDE_HOME_DIRECTORY_NAME = ".claude"
VERDICT_DIRECTORY_NAME = "verification"
VERDICT_KEY_ALL_PASS = "all_pass"
VERDICT_KEY_MANIFEST_SHA256 = "manifest_sha256"
DOCS_ONLY_EXTENSIONS = frozenset(
    {".md", ".txt", ".rst", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}
)
PYTHON_EXTENSION = ".py"
MINIMUM_STATUS_FIELD_COUNT = 2
ALL_FALLBACK_BASE_REFERENCES = ("origin/main", "origin/master")
ALL_TOOLING_STATE_PREFIXES = (".claude/", ".cursor/")
GATED_GIT_SUBCOMMANDS = frozenset({"commit", "push"})
VALUE_TAKING_GIT_OPTIONS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
REPO_DIRECTORY_OPTION = "-C"
OPTION_WITH_VALUE_STEP = 2
ALL_GATED_TOOL_NAMES = ("Bash", "PowerShell")
HASH_PREVIEW_LENGTH = 16
MINTING_AGENT_TYPE = "fable-verifier"
CORRECTIVE_MESSAGE = (
    "BLOCKED: [VERIFIED_COMMIT_GATE] This branch surface has no passing "
    "verification verdict. Spawn the fable-verifier agent (Agent tool, "
    "subagent_type 'fable-verifier') with the task texts, the diff scope, "
    "and recorded baselines; when it finishes with a clean verdict the "
    "SubagentStop hook mints the verdict and this command will pass. Any "
    "file change after verification invalidates the verdict, so verify "
    "last. Docs-, docstring-, and comment-only surfaces are exempt "
    "automatically."
)
