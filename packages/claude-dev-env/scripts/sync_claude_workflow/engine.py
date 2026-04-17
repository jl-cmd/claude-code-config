"""Pure logic for syncing the canonical claude.yml to downstream caller repos."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

from sync_claude_workflow.config import (
    CANONICAL_WORKFLOW_PATH_IN_THIS_REPO,
    EXIT_CODE_CONFIG_ERROR,
    EXIT_CODE_PARTIAL_FAILURE,
    EXIT_CODE_SUCCESS,
    GH_API_NOT_FOUND_STDERR_TOKEN,
    PAYLOAD_PREVIEW_CHARACTER_LIMIT,
    SYNC_COMMIT_MESSAGE,
    TARGET_DEFAULT_BRANCH,
    TARGET_REPOS,
    TARGET_WORKFLOW_PATH,
)


def resolve_repo_root() -> Path:
    script_file = Path(__file__).resolve()
    for candidate in (script_file, *script_file.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError("Could not locate repository root from script location")


def read_canonical_workflow_bytes(repo_root: Path) -> bytes:
    canonical_path = repo_root / CANONICAL_WORKFLOW_PATH_IN_THIS_REPO
    if not canonical_path.exists():
        raise FileNotFoundError(f"Canonical workflow missing: {canonical_path}")
    return canonical_path.read_bytes()


def fetch_remote_file_metadata(repository_full_name: str) -> dict[str, str] | None:
    api_path = f"repos/{repository_full_name}/contents/{TARGET_WORKFLOW_PATH}"
    completed = subprocess.run(
        ["gh", "api", api_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        if GH_API_NOT_FOUND_STDERR_TOKEN in completed.stderr:
            return None
        raise RuntimeError(f"gh api {api_path} failed: {completed.stderr.strip()}")
    try:
        decoded_payload = json.loads(completed.stdout)
    except json.JSONDecodeError as decode_error:
        raise RuntimeError(
            f"gh api {api_path} returned non-JSON stdout: {decode_error}"
        ) from decode_error
    if not isinstance(decoded_payload, dict) or "sha" not in decoded_payload or "content" not in decoded_payload:
        payload_preview = repr(decoded_payload)[:PAYLOAD_PREVIEW_CHARACTER_LIMIT]
        raise RuntimeError(
            f"unexpected API response shape for {repository_full_name}: {payload_preview}"
        )
    return {
        "sha": decoded_payload["sha"],
        "content_base64": decoded_payload["content"].replace("\n", ""),
    }


def remote_matches_canonical(
    remote_metadata: dict[str, str] | None,
    canonical_bytes: bytes,
) -> bool:
    if remote_metadata is None:
        return False
    remote_bytes = base64.b64decode(remote_metadata["content_base64"])
    return remote_bytes == canonical_bytes


def push_canonical_to_repo(
    repository_full_name: str,
    canonical_bytes: bytes,
    remote_metadata: dict[str, str] | None,
    dry_run: bool,
) -> bool:
    api_path = f"repos/{repository_full_name}/contents/{TARGET_WORKFLOW_PATH}"
    request_body: dict[str, str] = {
        "message": SYNC_COMMIT_MESSAGE,
        "content": base64.b64encode(canonical_bytes).decode("ascii"),
        "branch": TARGET_DEFAULT_BRANCH,
    }
    if remote_metadata is not None:
        request_body["sha"] = remote_metadata["sha"]

    if dry_run:
        action_label = "UPDATE" if remote_metadata else "CREATE"
        print(f"  [dry-run] would {action_label} {api_path}")
        return True

    completed = subprocess.run(
        ["gh", "api", "-X", "PUT", api_path, "--input", "-"],
        input=json.dumps(request_body),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        print(f"  FAILED (push): {completed.stderr.strip()}", file=sys.stderr)
        return False
    return True


def sync_single_repo(
    repository_full_name: str,
    canonical_bytes: bytes,
    dry_run: bool,
) -> bool:
    print(f"- {repository_full_name}")
    try:
        remote_metadata = fetch_remote_file_metadata(repository_full_name)
    except RuntimeError as fetch_error:
        print(f"  FAILED (fetch): {fetch_error}", file=sys.stderr)
        return False

    if remote_matches_canonical(remote_metadata, canonical_bytes):
        print("  up to date")
        return True

    return push_canonical_to_repo(
        repository_full_name, canonical_bytes, remote_metadata, dry_run
    )


def select_target_repos(only_filter: list[str]) -> tuple[str, ...]:
    if not only_filter:
        return TARGET_REPOS
    all_unknown_filters = [each_repo for each_repo in only_filter if each_repo not in TARGET_REPOS]
    if all_unknown_filters:
        all_unknown_names = ", ".join(all_unknown_filters)
        raise ValueError(f"unknown --only filter(s) not in TARGET_REPOS: {all_unknown_names}")
    return tuple(each_repo for each_repo in only_filter if each_repo in TARGET_REPOS)


def parse_command_line_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync the canonical claude.yml caller workflow across downstream repos."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing to any repo",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="OWNER/REPO",
        help="Sync a subset of target repos; may be passed multiple times",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_command_line_arguments()
    repo_root = resolve_repo_root()
    try:
        canonical_bytes = read_canonical_workflow_bytes(repo_root)
    except FileNotFoundError as missing_canonical_error:
        print(f"FAILED (config): {missing_canonical_error}", file=sys.stderr)
        return EXIT_CODE_CONFIG_ERROR
    try:
        selected_repos = select_target_repos(arguments.only)
    except ValueError as unknown_filter_error:
        print(f"FAILED (config): {unknown_filter_error}", file=sys.stderr)
        return EXIT_CODE_CONFIG_ERROR

    print(
        f"Syncing {TARGET_WORKFLOW_PATH} to {len(selected_repos)} repo(s) "
        f"({'dry run' if arguments.dry_run else 'live'}):"
    )

    all_failed_repos: list[str] = []
    for each_repo in selected_repos:
        if not sync_single_repo(each_repo, canonical_bytes, arguments.dry_run):
            all_failed_repos.append(each_repo)

    if all_failed_repos:
        print(
            f"\n{len(all_failed_repos)} repo(s) failed: {', '.join(all_failed_repos)}",
            file=sys.stderr,
        )
        return EXIT_CODE_PARTIAL_FAILURE
    print("\nAll target repos up to date.")
    return EXIT_CODE_SUCCESS
