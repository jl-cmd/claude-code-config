"""Mark a draft PR as ready for review.

Convergence action invoked by pr-converge when both bugbot and bugteam are
clean against the same HEAD.
"""

import argparse
import subprocess
import sys


def mark_pr_ready(*, owner: str, repo: str, number: int) -> None:
    """Run `gh pr ready <number> --repo <owner>/<repo>`."""
    gh_command: list[str] = [
        "gh",
        "pr",
        "ready",
        str(number),
        "--repo",
        f"{owner}/{repo}",
    ]
    subprocess.run(
        gh_command,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    mark_pr_ready(owner=parsed_arguments.owner, repo=parsed_arguments.repo, number=parsed_arguments.number)
    return 0


if __name__ == "__main__":
    sys.exit(main())
