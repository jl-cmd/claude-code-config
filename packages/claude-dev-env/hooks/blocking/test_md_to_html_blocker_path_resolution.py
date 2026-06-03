"""Tests for md_to_html_blocker path resolution, denial payload, and config.

Covers home-relative and tilde path canonicalization, the OS temp-directory
exemption, cwd-relative resolution against repo and plugin roots, the structure
of the denial payload (system message, additional context, redirect reason),
and the module-introspection contracts that pin centralized constants.
"""

import importlib
import json
import os
import subprocess
import sys
import tempfile

_BLOCKING_DIRECTORY = os.path.dirname(__file__)

if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)

from _md_to_html_blocker_test_support import (  # noqa: E402
    HOOK_SCRIPT_PATH,
    _get_sandbox_parent_directory,
    _run_hook,
)


def test_block_messages_mention_claude_dev_env_source_exemptions():
    """Block messages must surface the `packages/claude-dev-env/<dir>/` anchored
    exemption so contributors aren't misled when a `.md` write is denied
    elsewhere. Ensures docs/, rules/, and system-prompts/ source files
    render as writable in the user-facing message."""
    hook_dir = os.path.dirname(HOOK_SCRIPT_PATH)
    if hook_dir not in sys.path:
        sys.path.insert(0, hook_dir)
    blocker_module = importlib.import_module("md_to_html_blocker")
    importlib.reload(blocker_module)

    context_message = blocker_module._block_context()
    system_message = blocker_module._block_system_message()
    combined_messages = context_message + " " + system_message
    assert "claude-dev-env" in combined_messages, (
        "Block messages must mention claude-dev-env source-directory exemption; "
        f"got context={context_message!r} system={system_message!r}"
    )


def test_module_imports_path_segments_from_hooks_constants():
    """The blocker pulls the two leading path segments (`packages` and
    `claude-dev-env`) through the centralised hooks_constants module rather
    than inlining them as raw string literals."""
    hook_dir = os.path.dirname(HOOK_SCRIPT_PATH)
    if hook_dir not in sys.path:
        sys.path.insert(0, hook_dir)
    blocker_module = importlib.import_module("md_to_html_blocker")
    importlib.reload(blocker_module)
    assert blocker_module.PACKAGES_TOP_LEVEL_SEGMENT == "packages"
    assert blocker_module.CLAUDE_DEV_ENV_REPO_NAME_SEGMENT == "claude-dev-env"


def test_module_imports_top_directories_from_hooks_constants():
    """The exempt-top-directories set must live in `hooks_constants/` rather
    than as a file-global single-use constant in the blocker module. The
    blocker imports the centralized constant; a regression that reintroduces
    a local module-scope copy would fail this assertion."""
    hook_dir = os.path.dirname(HOOK_SCRIPT_PATH)
    if hook_dir not in sys.path:
        sys.path.insert(0, hook_dir)
    blocker_module = importlib.import_module("md_to_html_blocker")
    importlib.reload(blocker_module)
    assert hasattr(blocker_module, "ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES"), (
        "Blocker module must import ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES from "
        "hooks_constants/ (file-global single-use rule)."
    )
    assert not hasattr(blocker_module, "_claude_code_source_top_directories"), (
        "Local _claude_code_source_top_directories must not be re-introduced; "
        "use the imported constant from hooks_constants/ instead."
    )


def test_blocks_relative_readme_when_cwd_is_not_repo_root():
    sandbox_parent = _get_sandbox_parent_directory()
    non_repo_cwd = os.path.join(sandbox_parent, "not-a-repo")
    os.makedirs(non_repo_cwd, exist_ok=True)
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "README.md", "content": "# README"},
        }
    )
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        cwd=non_repo_cwd,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denial_has_system_message():
    result = _run_hook(
        "Write",
        {"file_path": "docs/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["suppressOutput"] is True
    assert isinstance(output["systemMessage"], str)
    assert len(output["systemMessage"]) > 0


def test_denial_has_additional_context():
    result = _run_hook(
        "Write",
        {"file_path": "docs/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    ctx = output["hookSpecificOutput"].get("additionalContext", "")
    assert "HTML" in ctx
    assert "thariqs.github.io" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_denial_reason_mentions_html_redirect():
    result = _run_hook(
        "Write",
        {"file_path": "docs/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    reason = output["hookSpecificOutput"]["permissionDecisionReason"]
    assert ".html" in reason.lower()


def test_passes_home_session_log_directory():
    home_directory = os.path.expanduser("~")
    session_log_path = os.path.join(home_directory, "SessionLog", "decisions", "note.md")
    result = _run_hook(
        "Write",
        {"file_path": session_log_path, "content": "# Note"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_home_claude_plans_directory():
    home_directory = os.path.expanduser("~")
    plans_path = os.path.join(home_directory, ".claude", "plans", "plan.md")
    result = _run_hook(
        "Write",
        {"file_path": plans_path, "content": "# Plan"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_home_directory_other_md_file():
    home_directory = os.path.expanduser("~")
    other_path = os.path.join(home_directory, "docs", "guide.md")
    result = _run_hook(
        "Write",
        {"file_path": other_path, "content": "# Guide"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_tilde_session_log_path():
    result = _run_hook(
        "Write",
        {"file_path": "~/SessionLog/decisions/note.md", "content": "# Note"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_tilde_claude_plans_path():
    result = _run_hook(
        "Write",
        {"file_path": "~/.claude/plans/plan.md", "content": "# Plan"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_tilde_other_home_md_file():
    result = _run_hook(
        "Write",
        {"file_path": "~/docs/guide.md", "content": "# Guide"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_system_temp_directory():
    temp_md_path = os.path.join(tempfile.gettempdir(), "bugteam-scratch", "pr-body.md")
    result = _run_hook(
        "Write",
        {"file_path": temp_md_path, "content": "# Scratch"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_relative_path_from_home_cwd():
    home_directory = os.path.expanduser("~")
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "SessionLog/decisions/note.md",
                "content": "# Note",
            },
        }
    )
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        cwd=home_directory,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_canonicalized_home_path():
    canonical_home = os.path.realpath(os.path.expanduser("~"))
    canonical_path = os.path.join(canonical_home, "SessionLog", "canonical-note.md")
    result = _run_hook(
        "Write",
        {"file_path": canonical_path, "content": "# Canonical"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_relative_path_under_cwd_plugin_root_marker(tmp_path):
    plugin_root = tmp_path / "plugin-cwd-repo"
    (plugin_root / ".claude-plugin").mkdir(parents=True)
    (plugin_root / "subdir").mkdir(parents=True)

    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "subdir/design.md",
                "content": "# Design",
            },
        }
    )
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(plugin_root),
    )
    assert result.returncode == 0
    assert result.stdout == ""
