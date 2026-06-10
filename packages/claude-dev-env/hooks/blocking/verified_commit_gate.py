"""PreToolUse gate: git commit/push lands only behind a minted verifier verdict.

Fires on Bash and PowerShell tool calls. When the command carries a
``git commit`` or ``git push``, the gate resolves the repository the command
targets, computes the live change-surface manifest against the merge base,
and allows the command only when one of these holds:

- the repository has no upstream base (scratch repos are out of scope),
- the surface is mechanically non-behavioral (docs/images by extension,
  Python files whose docstring-stripped AST is unchanged), or
- a verdict minted by ``verifier_verdict_minter.py`` reports ``all_pass``
  and binds to the exact live manifest hash.

The surface binds every changed and untracked file's content, so slicing
work into small commits or staging files cannot move the hash, while any
content edit or new file after verification invalidates the verdict.
Verdict files live under ``~/.claude/verification/`` and are minted only by
the SubagentStop hook when a ``fable-verifier`` agent finishes.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

blocking_directory = str(Path(__file__).resolve().parent)
if blocking_directory not in sys.path:
    sys.path.insert(0, blocking_directory)

from config.verified_commit_constants import (
    CORRECTIVE_MESSAGE,
    GATED_GIT_SUBCOMMANDS,
    ALL_GATED_TOOL_NAMES,
    HASH_PREVIEW_LENGTH,
    OPTION_WITH_VALUE_STEP,
    REPO_DIRECTORY_OPTION,
    VALUE_TAKING_GIT_OPTIONS,
)
from verification_verdict_store import (    branch_surface_manifest,
    is_docs_only_diff,
    load_valid_verdict,
    manifest_sha256,
    resolve_merge_base,
    resolve_repo_root,
)


def _strip_token_quotes(token_text: str) -> str:
    """Remove quote characters from a token's edges.

    Tokens cut from inside a quoted shell-wrapper argument can carry an
    unpaired edge quote (``push"``), so both edges are stripped rather
    than only matched pairs.

    Args:
        token_text: One quote-aware token from a command string.

    Returns:
        The token without leading or trailing quote characters.
    """
    return token_text.strip("\"'")


def _gated_invocation_directory(all_following_tokens: list[str]) -> tuple[bool, str | None]:
    """Walk the tokens after a ``git`` word to its first subcommand.

    Skips git's global options (recording the ``-C`` directory when one
    appears) so a gated verb counts only in subcommand position — never as
    an argument like ``git stash push`` or ``git log --grep commit``.

    Args:
        all_following_tokens: Quote-stripped tokens after the ``git`` word.

    Returns:
        Whether the first subcommand is gated, and the ``-C`` directory
        when the invocation carries one.
    """
    repo_directory: str | None = None
    token_index = 0
    while token_index < len(all_following_tokens):
        each_token = all_following_tokens[token_index]
        if each_token in VALUE_TAKING_GIT_OPTIONS:
            if each_token == REPO_DIRECTORY_OPTION and token_index + 1 < len(
                all_following_tokens
            ):
                repo_directory = all_following_tokens[token_index + 1]
            token_index += OPTION_WITH_VALUE_STEP
            continue
        if each_token.startswith("-"):
            token_index += 1
            continue
        return (each_token.lower() in GATED_GIT_SUBCOMMANDS, repo_directory)
    return (False, repo_directory)


def gated_repo_directories(command_text: str, fallback_directory: str) -> list[str]:
    """Collect the directories of every git commit/push found in a command.

    Scans every ``git`` word in the command — including inside quoted
    shell-wrapper arguments — and token-walks from each to its first
    subcommand.

    Args:
        command_text: The raw command string from the tool payload.
        fallback_directory: The session working directory, used when the git
            call carries no ``-C`` flag.

    Returns:
        One directory per detected commit/push invocation, in order; empty
        when the command carries no gated git verb.
    """
    git_word_pattern = re.compile(r"\bgit\b", re.IGNORECASE)
    command_token_pattern = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")
    target_directories: list[str] = []
    for each_git_match in git_word_pattern.finditer(command_text):
        following_text = command_text[each_git_match.end():]
        all_following_tokens = [
            _strip_token_quotes(each_token)
            for each_token in command_token_pattern.findall(following_text)
        ]
        is_gated, flagged_directory = _gated_invocation_directory(all_following_tokens)
        if is_gated:
            target_directories.append(flagged_directory or fallback_directory)
    return target_directories


def deny_reason_for_directory(target_directory: str) -> str | None:
    """Decide whether a commit/push in a directory must be blocked.

    Args:
        target_directory: The directory the git command targets.

    Returns:
        The deny reason when the branch diff needs a verdict and none binds
        to it; None when the command may proceed.
    """
    repo_root = resolve_repo_root(target_directory)
    if repo_root is None:
        return None
    merge_base_sha = resolve_merge_base(repo_root)
    if merge_base_sha is None:
        return None
    if is_docs_only_diff(repo_root, merge_base_sha):
        return None
    surface_manifest_text = branch_surface_manifest(repo_root, merge_base_sha)
    if surface_manifest_text is None:
        return f"{CORRECTIVE_MESSAGE} (surface manifest failed in {repo_root})"
    live_manifest_sha256 = manifest_sha256(surface_manifest_text)
    if load_valid_verdict(repo_root, live_manifest_sha256) is None:
        hash_preview = live_manifest_sha256[:HASH_PREVIEW_LENGTH]
        return f"{CORRECTIVE_MESSAGE} (repo: {repo_root}, surface sha256 {hash_preview}...)"
    return None


def main() -> None:
    """Read the PreToolUse payload and deny unverified commit/push commands."""
    try:
        pretooluse_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    if pretooluse_payload.get("tool_name", "") not in ALL_GATED_TOOL_NAMES:
        return
    command_text = pretooluse_payload.get("tool_input", {}).get("command", "")
    if not command_text:
        return
    session_directory = pretooluse_payload.get("cwd", ".")
    for each_target_directory in gated_repo_directories(command_text, session_directory):
        deny_reason = deny_reason_for_directory(each_target_directory)
        if deny_reason is None:
            continue
        deny_payload = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        }
        print(json.dumps(deny_payload))
        return


if __name__ == "__main__":
    main()
