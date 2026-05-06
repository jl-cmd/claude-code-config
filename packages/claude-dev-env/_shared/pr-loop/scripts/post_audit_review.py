"""Post a PR review with inline findings using gh api.

Step 1: POST a review summary (COMMENT event) to the reviews endpoint.
Step 2: POST each finding as an inline review comment anchored to the diff.
"""

import argparse
import json
import sys
from pathlib import Path

sys.modules.pop("config", None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.gh_util_constants import DEFAULT_TIMEOUT_SECONDS
from config.review_posting_constants import (
    COMMENT_POST_ENDPOINT_TEMPLATE,
    GH_FIELD_BODY_AT_PREFIX,
    REVIEW_COMMENTS_SIDE,
    REVIEW_EVENT_COMMENT,
    REVIEW_POST_ENDPOINT_TEMPLATE,
)
from gh_util import run_gh


def post_review_summary(
    *,
    owner: str,
    repo: str,
    pull_number: int,
    commit_id: str,
    body_file: Path,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[str, str] | None:
    """Post a review summary COMMENT on a pull request, return (id, html_url)."""
    endpoint_path = REVIEW_POST_ENDPOINT_TEMPLATE.format(
        owner=owner, repo=repo, pull_number=pull_number
    )
    gh_result = run_gh(
        [
            "gh",
            "api",
            endpoint_path,
            "-X",
            "POST",
            "-f",
            f"commit_id={commit_id}",
            "-f",
            f"event={REVIEW_EVENT_COMMENT}",
            "-F",
            f"{GH_FIELD_BODY_AT_PREFIX}{body_file}",
        ],
        timeout_seconds=timeout_seconds,
        retry_nonzero=False,
        retry_timeout=False,
    )
    if gh_result.returncode != 0:
        error_text = (gh_result.stderr or "").strip() or gh_result.stdout.strip()
        print(f"Review POST failed: {error_text}", file=sys.stderr)
        return None
    return _parse_identifier_and_url(gh_result.stdout, "review")


def post_comment(
    *,
    owner: str,
    repo: str,
    pull_number: int,
    commit_id: str,
    body_file: Path,
    path: str,
    line: int,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[str, str] | None:
    """Post an inline review comment on a pull request, return (id, html_url)."""
    endpoint_path = COMMENT_POST_ENDPOINT_TEMPLATE.format(
        owner=owner, repo=repo, pull_number=pull_number
    )
    gh_result = run_gh(
        [
            "gh",
            "api",
            endpoint_path,
            "-X",
            "POST",
            "-F",
            f"{GH_FIELD_BODY_AT_PREFIX}{body_file}",
            "-f",
            f"commit_id={commit_id}",
            "-f",
            f"path={path}",
            "-F",
            f"line={line}",
            "-f",
            f"side={REVIEW_COMMENTS_SIDE}",
        ],
        timeout_seconds=timeout_seconds,
        retry_nonzero=False,
        retry_timeout=False,
    )
    if gh_result.returncode != 0:
        return None
    return _parse_identifier_and_url(gh_result.stdout, "comment")


def _parse_identifier_and_url(
    response_text: str,
    label: str,
) -> tuple[str, str] | None:
    """Extract id and html_url from a gh API POST response JSON."""
    try:
        response_payload = json.loads(response_text)
    except json.JSONDecodeError:
        print(f"Failed to decode {label} response JSON.", file=sys.stderr)
        return None
    raw_identifier = response_payload.get("id")
    raw_url = response_payload.get("html_url")
    if not isinstance(raw_identifier, (int, str)) or not isinstance(raw_url, str):
        print(f"{label} response missing id or html_url.", file=sys.stderr)
        return None
    return (str(raw_identifier), raw_url)




def _build_output_payload(
    review_identifier: str,
    review_url: str,
    all_comment_results: list[tuple[str, str]],
) -> str:
    """Build the JSON output string written to stdout on success."""
    output_payload: dict[str, object] = {
        "review_id": review_identifier,
        "review_url": review_url,
        "comments": [
            {"id": each_identifier, "url": each_url}
            for each_identifier, each_url in all_comment_results
        ],
    }
    return json.dumps(output_payload)


def main(all_arguments: list[str], timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> int:
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
    review_result = post_review_summary(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        pull_number=parsed_arguments.number,
        commit_id=parsed_arguments.commit_id,
        body_file=parsed_arguments.body_file,
        timeout_seconds=timeout_seconds,
    )
    if review_result is None:
        return 1
    review_identifier, review_url = review_result
    all_comment_results: list[tuple[str, str]] = []
    if finding_count > 0:
        for each_index, each_finding_file in enumerate(all_finding_files):
            each_path = all_paths[each_index]
            each_line = all_lines[each_index]
            comment_result = post_comment(
                owner=parsed_arguments.owner,
                repo=parsed_arguments.repo,
                pull_number=parsed_arguments.number,
                commit_id=parsed_arguments.commit_id,
                body_file=each_finding_file,
                path=each_path,
                line=each_line,
                timeout_seconds=timeout_seconds,
            )
            if comment_result is None:
                finding_number = each_index + 1
                print(
                    f"Review already posted at {review_url}",
                    file=sys.stderr,
                )
                print(
                    f"Failed to post finding {finding_number}/{finding_count}: "
                    f"{each_finding_file}",
                    file=sys.stderr,
                )
                return 1
            all_comment_results.append(comment_result)
    output_text = _build_output_payload(
        review_identifier, review_url, all_comment_results
    )
    print(output_text)
    return 0


def _parse_arguments(all_arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post a PR review summary with inline findings.",
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
