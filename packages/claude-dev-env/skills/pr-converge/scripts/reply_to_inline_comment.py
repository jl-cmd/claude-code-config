"""Post an inline reply to a PR review comment.

Reply body is sourced from a file via `gh api ... -F body=@<path>` (per the
gh-body-file rule — passing a string body to gh can corrupt backticks).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.modules.pop("config", None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.pr_converge_constants import GH_INLINE_COMMENT_REPLY_PATH_TEMPLATE


def reply_to_inline_comment(
    *,
    owner: str,
    repo: str,
    number: int,
    comment_id: int,
    body_file: Path,
) -> int:
    """POST an inline reply to a PR review comment, return gh's reply id."""
    replies_endpoint = GH_INLINE_COMMENT_REPLY_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number, comment_id=comment_id
    )
    gh_command: list[str] = [
        "gh",
        "api",
        "-X",
        "POST",
        replies_endpoint,
        "-F",
        f"body=@{body_file}",
    ]
    completed = subprocess.run(
        gh_command,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    response_payload: dict[str, object] = json.loads(completed.stdout)
    return int(response_payload["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parser.add_argument("--comment-id", required=True, type=int, dest="comment_id")
    parser.add_argument("--body-file", required=True, type=Path, dest="body_file")
    parsed_arguments = parser.parse_args()
    reply_id = reply_to_inline_comment(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        number=parsed_arguments.number,
        comment_id=parsed_arguments.comment_id,
        body_file=parsed_arguments.body_file,
    )
    sys.stdout.write(f"{reply_id}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
