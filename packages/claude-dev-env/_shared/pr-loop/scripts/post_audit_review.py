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
    REVIEW_COMMENTS_ENDPOINT_TEMPLATE,
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

    Per the GitHub REST API, POST /reviews does not echo the inline child
    comments in its response. After the POST succeeds, fetch the inline
    comments via GET /reviews/{review_id}/comments and merge them into the
    return value so callers can route per-finding replies.
    """
    review_endpoint_path = REVIEW_POST_ENDPOINT_TEMPLATE.format(
        owner=owner, repo=repo, pull_number=pull_number
    )
    request_payload: dict[str, object] = {
        "commit_id": commit_id,
        "event": REVIEW_EVENT_COMMENT,
        "body": body_text,
        "comments": all_comments,
    }
    payload_text = json.dumps(request_payload)
    post_result = run_gh(
        ["gh", "api", review_endpoint_path, "-X", "POST", "--input", "-"],
        timeout_seconds=REVIEW_POST_TIMEOUT_SECONDS,
        should_retry_nonzero=False,
        should_retry_timeout=False,
        stdin_text=payload_text,
    )
    if post_result.is_timed_out:
        print(
            "Review POST timed out -- review may already exist. "
            "Check PR for conflicts before fallback.",
            file=sys.stderr,
        )
        return None
    if post_result.returncode != 0:
        error_text = (post_result.stderr or "").strip() or post_result.stdout.strip()
        print(f"Review POST failed: {error_text}", file=sys.stderr)
        return None
    parsed_review = _parse_review_response(post_result.stdout)
    if parsed_review is None:
        return None
    review_identifier, review_url, _ = parsed_review
    if not all_comments:
        return (review_identifier, review_url, [])
    all_inline_comment_entries = _fetch_inline_review_comments(
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        review_identifier=review_identifier,
    )
    return (review_identifier, review_url, all_inline_comment_entries)


def _fetch_inline_review_comments(
    *,
    owner: str,
    repo: str,
    pull_number: int,
    review_identifier: str,
) -> list[dict[str, str]]:
    """Fetch inline child comments for a posted review via paginated GET.

    On any failure (non-zero gh exit, malformed JSON), log to stderr and
    return an empty list. The parent review POST already succeeded, so a
    follow-up failure is non-fatal — callers may still route generic replies
    against the parent review url.
    """
    comments_endpoint_path = REVIEW_COMMENTS_ENDPOINT_TEMPLATE.format(
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        review_id=review_identifier,
    )
    fetch_result = run_gh(
        [
            "gh",
            "-R",
            f"{owner}/{repo}",
            "api",
            comments_endpoint_path,
            "--paginate",
            "--slurp",
        ],
        timeout_seconds=REVIEW_POST_TIMEOUT_SECONDS,
        should_retry_nonzero=True,
        should_retry_timeout=True,
    )
    if fetch_result.returncode != 0:
        error_text = (fetch_result.stderr or "").strip() or fetch_result.stdout.strip()
        print(
            f"Inline review comments GET failed: {error_text}",
            file=sys.stderr,
        )
        return []
    return _parse_inline_comments_response(fetch_result.stdout)


def _parse_inline_comments_response(raw_stdout: str) -> list[dict[str, str]]:
    """Parse paginated-slurp inline comments output into id/url entries.

    Mirrors the defensive shape used by `_parse_paginated_slurp_response` in
    verify_review.py: the root must be a list-of-pages, each page a list,
    each item a dict with both id and html_url. Anything else returns [].
    """
    try:
        parsed_pages = json.loads(raw_stdout)
    except json.JSONDecodeError:
        print("Failed to decode inline comments response JSON.", file=sys.stderr)
        return []
    if not isinstance(parsed_pages, list):
        print("Inline comments response was not a JSON list.", file=sys.stderr)
        return []
    all_inline_entries: list[dict[str, str]] = []
    for each_page in parsed_pages:
        if not isinstance(each_page, list):
            continue
        for each_comment in each_page:
            if not isinstance(each_comment, dict):
                continue
            each_id = each_comment.get("id")
            each_url = each_comment.get("html_url")
            if isinstance(each_id, (int, str)) and isinstance(each_url, str):
                all_inline_entries.append({"id": str(each_id), "url": each_url})
    return all_inline_entries


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
    if not isinstance(parsed_review_object, dict):
        print("Review response was not a JSON object.", file=sys.stderr)
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
    serialized_review_summary = _build_output_payload(
        review_identifier, review_url, all_comment_entries
    )
    print(serialized_review_summary)
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
