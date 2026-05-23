#!/usr/bin/env python3
"""PreToolUse hook: gate pr-converge fix pushes on code_rules_gate before they land.

Fires on a git push (Bash) or a GitHub MCP write call while a managed pr-converge
or bugteam loop is active in the worktree. Runs code_rules_gate.py over the PR diff
and denies the push when the gate reports a blocking violation, so a fix-induced
CODE_RULES regression is caught in the same loop that introduced it rather than at
the next loop's pre-audit. On a definitive gate run it records the outcome in a
worktree-scoped gate-result file the Stop backstop reads.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.fix_push_gate_constants import (  # noqa: E402
    ALL_GATED_MCP_WRITE_TOOLS,
    ALL_GH_PR_VIEW_IDENTITY_COMMAND,
    ALL_GIT_HEAD_SHA_COMMAND,
    ALL_GIT_SHOW_TOPLEVEL_COMMAND,
    BASH_TOOL_NAME,
    CODE_RULES_GATE_INSTALLED_RELATIVE_PATH,
    DENY_REASON_TEMPLATE,
    GATE_BASE_REF_TEMPLATE,
    GATE_EXIT_BLOCKING,
    GATE_EXIT_CLEAN,
    GATE_RESULT_FILENAME_TEMPLATE,
    GIT_PUSH_COMMAND_PATTERN,
    LOOP_OUTCOMES_GLOB,
    LOOP_STATE_FILENAME,
)


def _is_gated_action(tool_name: str, command: str) -> bool:
    """Return True when this tool call is a push the gate should evaluate.

    Args:
        tool_name: The tool name from the hook payload.
        command: The Bash command string (empty for non-Bash tools).

    Returns:
        True for a GitHub MCP write tool or a Bash command that pushes to a
        git remote; False otherwise.
    """
    if tool_name in ALL_GATED_MCP_WRITE_TOOLS:
        return True
    if tool_name == BASH_TOOL_NAME:
        return bool(GIT_PUSH_COMMAND_PATTERN.search(command))
    return False


def _resolve_repo_root(cwd: str | None) -> Path | None:
    """Return the git worktree root for *cwd*, or None when not a repo."""
    completed_process = subprocess.run(
        list(ALL_GIT_SHOW_TOPLEVEL_COMMAND),
        capture_output=True,
        text=True,
        cwd=cwd or None,
        check=False,
    )
    if completed_process.returncode != 0:
        return None
    top_level = completed_process.stdout.strip()
    if not top_level:
        return None
    return Path(top_level)


def _loop_is_active(repo_root: Path) -> bool:
    """Return True when the worktree shows an active pr-converge/bugteam loop.

    Args:
        repo_root: The git worktree root.

    Returns:
        True when ``pr-converge-state.json`` or a bugteam per-loop outcomes
        file is present in the worktree root; False otherwise.
    """
    if (repo_root / LOOP_STATE_FILENAME).is_file():
        return True
    return any(repo_root.glob(LOOP_OUTCOMES_GLOB))


def _resolve_pr_identity(cwd: str | None) -> tuple[int, str] | None:
    """Return ``(pr_number, base_ref)`` for the current branch's open PR.

    Args:
        cwd: Working directory for the ``gh`` invocation.

    Returns:
        A ``(pr_number, base_ref)`` tuple, or None when no open PR resolves
        or the response is malformed.
    """
    completed_process = subprocess.run(
        list(ALL_GH_PR_VIEW_IDENTITY_COMMAND),
        capture_output=True,
        text=True,
        cwd=cwd or None,
        check=False,
    )
    if completed_process.returncode != 0:
        return None
    try:
        pr_payload = json.loads(completed_process.stdout)
    except json.JSONDecodeError:
        return None
    pr_number = pr_payload.get("number")
    base_ref = pr_payload.get("baseRefName")
    if not isinstance(pr_number, int) or not isinstance(base_ref, str) or not base_ref:
        return None
    return pr_number, base_ref


def _resolve_head_sha(repo_root: Path) -> str | None:
    """Return the current HEAD SHA for *repo_root*, or None on failure."""
    completed_process = subprocess.run(
        list(ALL_GIT_HEAD_SHA_COMMAND),
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )
    if completed_process.returncode != 0:
        return None
    head_sha = completed_process.stdout.strip()
    return head_sha or None


def _locate_gate_script() -> Path | None:
    """Return the installed code_rules_gate.py path, or None when absent."""
    gate_script = Path.home() / CODE_RULES_GATE_INSTALLED_RELATIVE_PATH
    if gate_script.is_file():
        return gate_script
    return None


def _run_gate(gate_script: Path, repo_root: Path, base_ref: str) -> tuple[int, str]:
    """Run code_rules_gate.py over the PR diff and capture its report.

    Args:
        gate_script: Path to the installed gate script.
        repo_root: The git worktree root passed as ``--repo-root``.
        base_ref: The PR base ref name (without the ``origin/`` prefix).

    Returns:
        A ``(returncode, combined_output)`` tuple where combined output joins
        the gate's stdout and stderr for inclusion in the deny reason.
    """
    completed_process = subprocess.run(
        [
            sys.executable,
            str(gate_script),
            "--repo-root",
            str(repo_root),
            "--base",
            GATE_BASE_REF_TEMPLATE.format(base_ref=base_ref),
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )
    return completed_process.returncode, completed_process.stdout + completed_process.stderr


def _write_gate_result(
    repo_root: Path,
    pr_number: int,
    passed: bool,
    head_sha: str | None,
    base_ref: str,
) -> None:
    """Record the gate verdict in the worktree-scoped gate-result file.

    Args:
        repo_root: The git worktree root the file is written into.
        pr_number: The PR number used in the filename.
        passed: Whether the gate reported the push as clean.
        head_sha: The HEAD SHA the verdict applies to.
        base_ref: The PR base ref the gate compared against.
    """
    gate_result_path = repo_root / GATE_RESULT_FILENAME_TEMPLATE.format(number=pr_number)
    gate_result_payload = {
        "passed": passed,
        "head_sha": head_sha,
        "base_ref": base_ref,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        gate_result_path.write_text(
            json.dumps(gate_result_payload) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _emit_deny(reason: str, into_stream: TextIO) -> None:
    """Write a PreToolUse deny decision carrying *reason* to *into_stream*.

    Args:
        reason: The ``permissionDecisionReason`` text shown to the agent.
        into_stream: Destination stream for the JSON decision (``sys.stdout``
            in production); accepting it as a parameter keeps the write off
            the bare ``sys.stdout.write`` path.
    """
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    into_stream.write(json.dumps(deny_payload) + "\n")
    into_stream.flush()


def main() -> None:
    """Gate the current push when a managed loop is active and the gate fails."""
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")

    if not _is_gated_action(tool_name, command):
        sys.exit(0)

    cwd = tool_input.get("cwd")
    repo_root = _resolve_repo_root(cwd)
    if repo_root is None:
        sys.exit(0)

    if not _loop_is_active(repo_root):
        sys.exit(0)

    pr_identity = _resolve_pr_identity(cwd)
    if pr_identity is None:
        sys.exit(0)
    pr_number, base_ref = pr_identity

    gate_script = _locate_gate_script()
    if gate_script is None:
        sys.exit(0)

    head_sha = _resolve_head_sha(repo_root)
    return_code, gate_output = _run_gate(gate_script, repo_root, base_ref)

    if return_code == GATE_EXIT_BLOCKING:
        _write_gate_result(repo_root, pr_number, False, head_sha, base_ref)
        _emit_deny(DENY_REASON_TEMPLATE.format(gate_output=gate_output), sys.stdout)
        sys.exit(0)

    if return_code == GATE_EXIT_CLEAN:
        _write_gate_result(repo_root, pr_number, True, head_sha, base_ref)
    sys.exit(0)


if __name__ == "__main__":
    main()
