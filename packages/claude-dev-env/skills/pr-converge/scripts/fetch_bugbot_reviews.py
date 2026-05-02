"""Fetch Cursor Bugbot reviews newest-first, classified as dirty or clean.

Wraps the gh CLI invocation required by the gh-paginate rule:
`gh api '...?per_page=100' --paginate --slurp` piped through external Python
JSON handling (instead of `gh --jq`, which runs per-page and breaks cross-page
operations like sort/reverse — see GitHub CLI #10459).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.modules.pop("config", None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.pr_converge_constants import (
    BUGBOT_DIRTY_BODY_REGEX,
    CURSOR_BOT_LOGIN,
    GH_REVIEWS_PATH_TEMPLATE,
)


def fetch_bugbot_reviews(
    *,
    owner: str,
    repo: str,
    number: int,
) -> list[dict]:
    """Return Cursor Bugbot reviews newest-first, each with a clean/dirty classification.

    Each entry contains review_id, commit_id, submitted_at, body, and classification.
    """
    cursor_bot_login = CURSOR_BOT_LOGIN
    reviews_endpoint = GH_REVIEWS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    gh_command: list[str] = [
        "gh",
        "api",
        reviews_endpoint,
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
    flat_reviews = [each_review for each_page in pages for each_review in each_page]
    bugbot_reviews = [
        each_review
        for each_review in flat_reviews
        if (each_review.get("user") or {}).get("login") == cursor_bot_login
    ]
    bugbot_reviews.sort(
        key=lambda each_review: each_review["submitted_at"], reverse=True
    )
    dirty_pattern = re.compile(BUGBOT_DIRTY_BODY_REGEX)
    return [
        {
            "review_id": each_review["id"],
            "commit_id": each_review.get("commit_id"),
            "submitted_at": each_review["submitted_at"],
            "body": each_review.get("body") or "",
            "classification": (
                "dirty"
                if dirty_pattern.search(each_review.get("body") or "")
                else "clean"
            ),
        }
        for each_review in bugbot_reviews
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    all_reviews = fetch_bugbot_reviews(
        owner=parsed_arguments.owner, repo=parsed_arguments.repo, number=parsed_arguments.number
    )
    json.dump(all_reviews, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
