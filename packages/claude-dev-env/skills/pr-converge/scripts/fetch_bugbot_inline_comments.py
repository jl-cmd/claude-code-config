"""Fetch unaddressed Cursor Bugbot inline comments anchored to a specific commit.

Wraps the gh CLI invocation required by the gh-paginate rule:
`gh api '...?per_page=100' --paginate --slurp` piped through external Python
JSON handling. Filters to cursor[bot] comments whose commit_id matches the
caller-supplied current HEAD SHA.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import (
    CURSOR_BOT_LOGIN,
    GH_INLINE_COMMENTS_PATH_TEMPLATE,
)


def fetch_bugbot_inline_comments(
    *,
    owner: str,
    repo: str,
    number: int,
    current_head: str,
) -> list[dict]:
    """Return cursor[bot] inline comments anchored to current_head.

    Each entry contains comment_id, commit_id, path, line, and body.
    """
    cursor_bot_login = CURSOR_BOT_LOGIN
    comments_endpoint = GH_INLINE_COMMENTS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    gh_command: list[str] = [
        "gh",
        "api",
        comments_endpoint,
        "--paginate",
        "--slurp",
    ]
    completed = subprocess.run(
        gh_command,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    pages: list[list[dict]] = json.loads(completed.stdout)
    flat_comments = [each_comment for each_page in pages for each_comment in each_page]
    return [
        {
            "comment_id": each_comment["id"],
            "commit_id": each_comment.get("commit_id"),
            "path": each_comment.get("path"),
            "line": each_comment.get("line"),
            "body": each_comment.get("body") or "",
        }
        for each_comment in flat_comments
        if (each_comment.get("user") or {}).get("login") == cursor_bot_login
        and each_comment.get("commit_id") == current_head
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parser.add_argument("--commit", required=True, dest="current_head")
    parsed_arguments = parser.parse_args()
    all_comments = fetch_bugbot_inline_comments(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        number=parsed_arguments.number,
        current_head=parsed_arguments.current_head,
    )
    json.dump(all_comments, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
