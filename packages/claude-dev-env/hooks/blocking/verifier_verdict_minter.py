"""SubagentStop hook: mint a commit-gate verdict when fable-verifier finishes.

Only this hook writes verdict files — the main session is denied writes to
the verdict directory, so a session cannot fabricate a passing verdict. When
a ``fable-verifier`` subagent stops, the hook pulls the verdict block out of
the agent's own transcript — the payload key ``agent_transcript_path``;
``transcript_path`` is the parent session's file and is never read, so text
printed by the main session can never mint — recomputes the live
change-surface hash for the session repository, and writes the verdict
bound to that hash. The companion
``verified_commit_gate.py`` (PreToolUse) then allows ``git commit`` /
``git push`` only while the work tree still matches the verified state.

The verifier's final message must end with a fenced block::

    ```verdict
    {"all_pass": true, "findings": []}
    ```

A missing or unparseable block mints nothing, which leaves the gate closed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

blocking_directory = str(Path(__file__).resolve().parent)
if blocking_directory not in sys.path:
    sys.path.insert(0, blocking_directory)

from verification_verdict_store import (    branch_surface_manifest,
    manifest_sha256,
    resolve_merge_base,
    resolve_repo_root,
    write_verdict,
)


def assistant_text_blocks(transcript_path: str) -> list[str]:
    """Collect every assistant text block from a transcript JSONL file.

    Args:
        transcript_path: Path to the subagent's transcript.

    Returns:
        The text of each assistant content block, in transcript order;
        empty when the file is missing or holds no assistant text.
    """
    collected_blocks: list[str] = []
    try:
        transcript_lines = (
            Path(transcript_path).read_text(encoding="utf-8", errors="replace").splitlines()
        )
    except OSError:
        return collected_blocks
    for each_line in transcript_lines:
        try:
            transcript_entry = json.loads(each_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(transcript_entry, dict):
            continue
        if transcript_entry.get("type") != "assistant":
            continue
        message_body = transcript_entry.get("message")
        if not isinstance(message_body, dict):
            continue
        content_blocks = message_body.get("content")
        if not isinstance(content_blocks, list):
            continue
        for each_block in content_blocks:
            if isinstance(each_block, dict) and each_block.get("type") == "text":
                block_text = each_block.get("text")
                if isinstance(block_text, str):
                    collected_blocks.append(block_text)
    return collected_blocks


def last_verdict_in_blocks(all_text_blocks: list[str]) -> dict | None:
    """Extract the final verdict fence from assistant text blocks.

    Args:
        all_text_blocks: Assistant text blocks in transcript order.

    Returns:
        The parsed verdict mapping carrying a boolean ``all_pass`` and a
        list ``findings``, or None when no block holds a wellformed fence.
    """
    verdict_fence_pattern = re.compile(r"```verdict\s*\n(.*?)```", re.DOTALL)
    fence_bodies: list[str] = []
    for each_block in all_text_blocks:
        fence_bodies.extend(verdict_fence_pattern.findall(each_block))
    for each_fence_body in reversed(fence_bodies):
        try:
            verdict_record = json.loads(each_fence_body)
        except json.JSONDecodeError:
            continue
        if not isinstance(verdict_record, dict):
            continue
        if not isinstance(verdict_record.get("all_pass"), bool):
            continue
        if not isinstance(verdict_record.get("findings"), list):
            continue
        return verdict_record
    return None


def mint_for_payload(subagent_stop_payload: dict) -> Path | None:
    """Mint a verdict file for a fable-verifier stop event.

    Args:
        subagent_stop_payload: The SubagentStop hook payload.

    Returns:
        The verdict file path when minted; None when the payload is not a
        fable-verifier stop, the transcript holds no verdict, or the
        session directory is not a work tree with an upstream base.
    """
    minting_agent_type = "fable-verifier"
    if subagent_stop_payload.get("agent_type") != minting_agent_type:
        return None
    agent_transcript_path = subagent_stop_payload.get("agent_transcript_path", "")
    if not agent_transcript_path:
        return None
    verdict_record = last_verdict_in_blocks(assistant_text_blocks(agent_transcript_path))
    if verdict_record is None:
        return None
    repo_root = resolve_repo_root(subagent_stop_payload.get("cwd", "."))
    if repo_root is None:
        return None
    merge_base_sha = resolve_merge_base(repo_root)
    if merge_base_sha is None:
        return None
    surface_manifest_text = branch_surface_manifest(repo_root, merge_base_sha)
    if surface_manifest_text is None:
        return None
    return write_verdict(
        repo_root,
        manifest_sha256(surface_manifest_text),
        verdict_record["all_pass"],
        verdict_record["findings"],
        str(subagent_stop_payload.get("agent_id", "")),
    )


def main() -> None:
    """Read the SubagentStop payload and mint a verdict when one applies."""
    try:
        subagent_stop_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    if not isinstance(subagent_stop_payload, dict):
        return
    mint_for_payload(subagent_stop_payload)


if __name__ == "__main__":
    main()
