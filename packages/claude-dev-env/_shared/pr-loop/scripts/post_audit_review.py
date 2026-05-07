"""Post a PR review with inline child comments using gh api.

Builds a single JSON payload with a review summary body and an array of
inline comments, then POSTs it to the reviews endpoint. All findings appear
as child comment threads under the parent review on GitHub.
"""

import argparse
import json
import sys
from pathlib import Path

sys.modules.pop("config", None)
if str(Path(__file__).absolute().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).absolute().parent))

from config.review_posting_constants import (
    REVIEW_COMMENTS_SIDE,
    REVIEW_EVENT_COMMENT,
    REVIEW_POST_ENDPOINT_TEMPLATE,
    REVIEW_POST_TIMEOUT_SECONDS,
)
from gh_util import run_gh


def post_review(
    *,
    owner: str,
    repo: str,
    pull_number: int,
    commit_id: str,
    body_text: str,
    all_comments: list[dict[str, object]],
) -> tuple[str, str, list[dict[str, str]]] | None:
    """Post a PR review with inline comments, return (review_id, review_url, comment_infos).

    Each comment_infos entry is {"id": str, "url": str} extracted from the
    response's nested comment objects when available.
    """
    endpoint_path = REVIEW_POST_ENDPOINT_TEMPLATE.format(
        owner=owner, repo=repo, pull_number=pull_number
    )
    request_payload: dict[str, object] = {
        "commit_id": commit_id,
        "event": REVIEW_EVENT_COMMENT,
        "body": body_text,
        "comments": all_comments,
    }
    payload_text = json.dumps(request_payload)
    gh_result = run_gh(
        ["gh", "api", endpoint_path, "-X", "POST", "--input", "-"],
        timeout_seconds=REVIEW_POST_TIMEOUT_SECONDS,
        should_retry_nonzero=False,
        should_retry_timeout=False,
        stdin_text=payload_text,
    )
    if gh_result.is_timed_out:
        print(
            "Review POST timed out -- review may already exist. "
            "Check PR for conflicts before fallback.",
            file=sys.stderr,
        )
        return None
    if gh_result.returncode != 0:
        error_text = (gh_result.stderr or "").strip() or gh_result.stdout.strip()
        print(f"Review POST failed: {error_text}", file=sys.stderr)
        return None
    return _parse_review_response(gh_result.stdout)


def _parse_review_response(
    response_text: str,
) -> tuple[str, str, list[dict[str, str]]] | None:
    """Extract review id, html_url, and any nested comment info from a review POST response.

    Per the GitHub REST API, the POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews
    response does not include inline comments — they are returned via a separate
    GET /reviews/{id}/comments call. A successful response with a parseable review
    object means GitHub created the inline comments server-side from the request
    payload; absence of a nested ``comments`` field is therefore expected and not
    a failure signal.
    """
    try:
        parsed_review_object = json.loads(response_text)
    except json.JSONDecodeError:
        print("Failed to decode review response JSON.", file=sys.stderr)
        return None
    raw_identifier = parsed_review_object.get("id")
    raw_url = parsed_review_object.get("html_url")
    if not isinstance(raw_identifier, (int, str)) or not isinstance(raw_url, str):
        print("Review response missing id or html_url.", file=sys.stderr)
        return None
    all_comment_entries: list[dict[str, str]] = []
    all_nested_comments = parsed_review_object.get("comments")
    if isinstance(all_nested_comments, list):
        for each_comment in all_nested_comments:
            if isinstance(each_comment, dict):
                each_id = each_comment.get("id")
                each_url = each_comment.get("html_url")
                if isinstance(each_id, (int, str)) and isinstance(each_url, str):
                    all_comment_entries.append({"id": str(each_id), "url": each_url})
    return (str(raw_identifier), raw_url, all_comment_entries)


def _build_output_payload(
    review_identifier: str,
    review_url: str,
    all_comment_entries: list[dict[str, str]],
) -> str:
    """Build the JSON output string written to stdout on success."""
    review_summary_payload: dict[str, object] = {
        "review_id": review_identifier,
        "review_url": review_url,
        "comments": all_comment_entries,
    }
    return json.dumps(review_summary_payload)


def main(
    all_arguments: list[str],
) -> int:
    parsed_arguments = _parse_arguments(all_arguments)
    all_finding_files = parsed_arguments.finding_file
    all_paths = parsed_arguments.path
    all_lines = parsed_arguments.line
    finding_count = len(all_finding_files)
    path_count = len(all_paths)
    line_count = len(all_lines)
    if not (finding_count == path_count == line_count):
        print(
            f"Finding argument mismatch: {finding_count} finding-files, "
            f"{path_count} paths, {line_count} lines. "
            "Each finding needs --finding-file, --path, and --line.",
            file=sys.stderr,
        )
        return 1

    body_text = parsed_arguments.body_file.read_text(encoding="utf-8")

    all_comments: list[dict[str, object]] = []
    for each_index, each_finding_file in enumerate(all_finding_files):
        finding_body = each_finding_file.read_text(encoding="utf-8")
        all_comments.append(
            {
                "path": all_paths[each_index],
                "line": all_lines[each_index],
                "side": REVIEW_COMMENTS_SIDE,
                "body": finding_body,
            }
        )

    posted_review = post_review(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        pull_number=parsed_arguments.number,
        commit_id=parsed_arguments.commit_id,
        body_text=body_text,
        all_comments=all_comments,
    )
    if posted_review is None:
        return 1
    review_identifier, review_url, all_comment_entries = posted_review
    output_text = _build_output_payload(
        review_identifier, review_url, all_comment_entries
    )
    print(output_text)
    return 0


def _parse_arguments(all_arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post a PR review with inline findings.",
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parser.add_argument("--commit-id", required=True, dest="commit_id")
    parser.add_argument("--body-file", required=True, type=Path, dest="body_file")
    parser.add_argument(
        "--finding-file",
        action="append",
        type=Path,
        required=False,
        default=[],
        dest="finding_file",
        help="Markdown file with the finding body (repeat per finding).",
    )
    parser.add_argument(
        "--path",
        action="append",
        required=False,
        default=[],
        help="Source file path for the finding (repeat per finding).",
    )
    parser.add_argument(
        "--line",
        action="append",
        type=int,
        required=False,
        default=[],
        help="Line number for the finding (repeat per finding).",
    )
    return parser.parse_args(all_arguments)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
