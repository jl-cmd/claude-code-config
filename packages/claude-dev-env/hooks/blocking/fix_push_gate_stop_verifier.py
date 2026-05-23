#!/usr/bin/env python3
"""Stop hook: backstop confirming the pushed fix HEAD passed code_rules_gate.

In a managed pr-converge/bugteam loop, this verifies that the current HEAD is
recorded as gate-passing in the worktree gate-result file. When the file does
not vouch for the current HEAD, it re-runs code_rules_gate over the PR diff and
blocks the turn on a blocking violation, so a push that bypassed the PreToolUse
gate (for example from a spawned subagent that did not inherit it) cannot
survive to turn end. It fires in the orchestrator session regardless of
subagent hook inheritance, and reuses the blocker's resolution helpers so the
two layers compute identical worktree, PR, HEAD, and gate values.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

_blocking_dir = str(Path(__file__).resolve().parent)
if _blocking_dir not in sys.path:
    sys.path.insert(0, _blocking_dir)
_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.fix_push_gate_constants import (  # noqa: E402
    GATE_EXIT_BLOCKING,
    GATE_RESULT_FILENAME_TEMPLATE,
    STOP_BLOCK_REASON_TEMPLATE,
)
from fix_push_gate_blocker import (  # noqa: E402
    _locate_gate_script,
    _loop_is_active,
    _resolve_head_sha,
    _resolve_pr_identity,
    _resolve_repo_root,
    _run_gate,
)


def _head_is_vouched(repo_root: Path, pr_number: int, head_sha: str) -> bool:
    """Return True when the gate-result file records *head_sha* as passing.

    Args:
        repo_root: The git worktree root holding the gate-result file.
        pr_number: PR number used to resolve the gate-result filename.
        head_sha: The current HEAD the file must vouch for.

    Returns:
        True when the file exists, ``passed`` is True, and its ``head_sha``
        equals *head_sha*; False otherwise.
    """
    gate_result_path = repo_root / GATE_RESULT_FILENAME_TEMPLATE.format(number=pr_number)
    try:
        recorded = json.loads(gate_result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return recorded.get("passed") is True and recorded.get("head_sha") == head_sha


def _emit_block(reason: str, into_stream: TextIO) -> None:
    """Write a Stop block decision carrying *reason* to *into_stream*.

    Args:
        reason: The block reason shown to the agent.
        into_stream: Destination stream for the JSON decision (``sys.stdout``
            in production); accepting it as a parameter keeps the write off
            the bare ``sys.stdout.write`` path.
    """
    block_payload = {
        "decision": "block",
        "reason": reason,
        "suppressOutput": True,
    }
    into_stream.write(json.dumps(block_payload) + "\n")
    into_stream.flush()


def main() -> None:
    """Block the turn when a pushed HEAD has no passing gate record and fails the gate."""
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("stop_hook_active", False):
        sys.exit(0)

    repo_root = _resolve_repo_root(None)
    if repo_root is None:
        sys.exit(0)

    if not _loop_is_active(repo_root):
        sys.exit(0)

    pr_identity = _resolve_pr_identity(None)
    if pr_identity is None:
        sys.exit(0)
    pr_number, base_ref = pr_identity

    head_sha = _resolve_head_sha(repo_root)
    if head_sha is None:
        sys.exit(0)

    if _head_is_vouched(repo_root, pr_number, head_sha):
        sys.exit(0)

    gate_script = _locate_gate_script()
    if gate_script is None:
        sys.exit(0)

    return_code, gate_output = _run_gate(gate_script, repo_root, base_ref)
    if return_code == GATE_EXIT_BLOCKING:
        _emit_block(
            STOP_BLOCK_REASON_TEMPLATE.format(
                head_sha=head_sha,
                base_ref=base_ref,
                gate_output=gate_output,
            ),
            sys.stdout,
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
