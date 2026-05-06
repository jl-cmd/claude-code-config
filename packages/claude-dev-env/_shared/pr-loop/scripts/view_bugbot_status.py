"""View the Cursor Bugbot check-run status for a pull request."""

import argparse
import json
import sys
from pathlib import Path

sys.modules.pop("config", None)
if str(Path(__file__).absolute().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).absolute().parent))

from config.bugbot_check_constants import (
    BUGBOT_CHECK_NAME,
    CHECK_RUNS_JQ_FILTER,
    CHECK_RUNS_PATH_TEMPLATE,
    PR_ENDPOINT_TEMPLATE,
    PR_HEAD_SHA_JQ_FILTER,
)
from gh_util import run_gh


def _resolve_head_sha(owner: str, repo: str, pull_number: int) -> str | None:
    pr_endpoint = PR_ENDPOINT_TEMPLATE.format(
        owner=owner, repo=repo, pull_number=pull_number
    )
    gh_result = run_gh(["gh", "api", pr_endpoint, "--jq", PR_HEAD_SHA_JQ_FILTER])
    if gh_result.returncode != 0:
        print("Failed to resolve PR head SHA", file=sys.stderr)
        return None
    return gh_result.stdout.strip()


def _fetch_bugbot_check_runs(
    owner: str, repo: str, sha: str
) -> list[dict[str, object]] | None:
    endpoint = CHECK_RUNS_PATH_TEMPLATE.format(owner=owner, repo=repo, sha=sha)
    gh_result = run_gh(["gh", "api", endpoint, "--jq", CHECK_RUNS_JQ_FILTER])
    if gh_result.returncode != 0:
        print("Failed to fetch check runs", file=sys.stderr)
        return None
    try:
        all_check_runs = json.loads(gh_result.stdout)
    except json.JSONDecodeError:
        print("Failed to parse check-runs response", file=sys.stderr)
        return None
    if not isinstance(all_check_runs, list):
        return None
    return [
        each_run
        for each_run in all_check_runs
        if isinstance(each_run, dict) and each_run.get("name") == BUGBOT_CHECK_NAME
    ]


def main(all_arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="View Cursor Bugbot check-run status for a PR."
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed = parser.parse_args(all_arguments)

    head_sha = _resolve_head_sha(parsed.owner, parsed.repo, parsed.number)
    if head_sha is None:
        return 1

    bugbot_runs = _fetch_bugbot_check_runs(parsed.owner, parsed.repo, head_sha)
    if bugbot_runs is None:
        return 1

    flattened = []
    for each_run in bugbot_runs:
        flattened.append(
            {
                "id": each_run.get("id"),
                "name": each_run.get("name"),
                "status": each_run.get("status"),
                "conclusion": each_run.get("conclusion"),
                "started_at": each_run.get("started_at"),
                "completed_at": each_run.get("completed_at"),
                "html_url": each_run.get("html_url"),
                "details_url": each_run.get("details_url"),
                "annotations_count": each_run.get("output", {}).get(
                    "annotations_count", 0
                ),
                "summary": each_run.get("output", {}).get("summary", ""),
            }
        )

    print(json.dumps({"head_sha": head_sha, "check_runs": flattened}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
