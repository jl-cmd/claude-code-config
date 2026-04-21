"""Pin tests for path_rewriter_constants — values consumed by es_exe_path_rewriter."""

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))


def test_bash_tool_name_is_bash() -> None:
    from hook_config.path_rewriter_constants import BASH_TOOL_NAME

    assert BASH_TOOL_NAME == "Bash"


def test_hook_event_name_is_pre_tool_use() -> None:
    from hook_config.path_rewriter_constants import HOOK_EVENT_NAME

    assert HOOK_EVENT_NAME == "PreToolUse"


def test_permission_allow_is_allow() -> None:
    from hook_config.path_rewriter_constants import PERMISSION_ALLOW

    assert PERMISSION_ALLOW == "allow"


def test_placeholder_token_pattern_matches_curly_brace_form() -> None:
    from hook_config.path_rewriter_constants import PLACEHOLDER_TOKEN_PATTERN

    match = PLACEHOLDER_TOKEN_PATTERN.match("{my-repo}")
    assert match is not None
    assert match.group(1) == "my-repo"


def test_placeholder_token_pattern_matches_double_quoted_form() -> None:
    from hook_config.path_rewriter_constants import PLACEHOLDER_TOKEN_PATTERN

    match = PLACEHOLDER_TOKEN_PATTERN.match('"{my-repo}"')
    assert match is not None
    assert match.group(1) == "my-repo"


def test_placeholder_token_pattern_matches_single_quoted_form() -> None:
    from hook_config.path_rewriter_constants import PLACEHOLDER_TOKEN_PATTERN

    match = PLACEHOLDER_TOKEN_PATTERN.match("'{my-repo}'")
    assert match is not None
    assert match.group(1) == "my-repo"
