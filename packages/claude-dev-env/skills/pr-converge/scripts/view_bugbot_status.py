"""View the Cursor Bugbot check-run status for a pull request.

Queries GitHub check-runs on the PR head commit and filters to the
Cursor Bugbot check run, reporting status and conclusion as JSON.
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
    BUGBOT_CHECK_NAME,
    CHECK_RUNS_JQ_FILTER,
    CHECK_RUNS_PATH_TEMPLATE,
    PR_ENDPOINT_TEMPLATE,
    PR_HEAD_SHA_JQ_FILTER,
    PR_NUMBER_ARG_FLAG,
    PR_NUMBER_ARG_HELP,
    PR_OWNER_ARG_FLAG,
    PR_OWNER_ARG_HELP,
    PR_REPO_ARG_FLAG,
    PR_REPO_ARG_HELP,
)


def _resolve_head_sha(owner: str, repo: str, pull_number: int) -> str | None:
    pr_endpoint = PR_ENDPOINT_TEMPLATE.format(
        owner=owner, repo=repo, pull_number=pull_number
    )
    completed = subprocess.run(
        ["gh", "api", pr_endpoint, "--jq", PR_HEAD_SHA_JQ_FILTER],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        error_text = completed.stderr.strip() or completed.stdout.strip()
        print(f"Failed to resolve PR head SHA: {error_text}", file=sys.stderr)
        return None
    return completed.stdout.strip()


def _fetch_bugbot_check_runs(
    owner: str, repo: str, sha: str
) -> list[dict[str, object]]:
    endpoint = CHECK_RUNS_PATH_TEMPLATE.format(owner=owner, repo=repo, sha=sha)
    completed = subprocess.run(
        ["gh", "api", endpoint, "--jq", CHECK_RUNS_JQ_FILTER],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        error_text = completed.stderr.strip() or completed.stdout.strip()
        print(f"Failed to fetch check runs: {error_text}", file=sys.stderr)
        return []
    try:
        all_check_runs = json.loads(completed.stdout)
    except json.JSONDecodeError:
        print("Failed to parse check-runs response", file=sys.stderr)
        return []
    if not isinstance(all_check_runs, list):
        return []
    return [
        each_run
        for each_run in all_check_runs
        if isinstance(each_run, dict) and each_run.get("name") == BUGBOT_CHECK_NAME
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        PR_NUMBER_ARG_FLAG, required=True, type=int, help=PR_NUMBER_ARG_HELP
    )
    parser.add_argument(PR_OWNER_ARG_FLAG, required=True, help=PR_OWNER_ARG_HELP)
    parser.add_argument(PR_REPO_ARG_FLAG, required=True, help=PR_REPO_ARG_HELP)
    parsed = parser.parse_args()

    head_sha = _resolve_head_sha(parsed.owner, parsed.repo, parsed.number)
    if head_sha is None:
        return 1

    bugbot_runs = _fetch_bugbot_check_runs(parsed.owner, parsed.repo, head_sha)
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

    json.dump({"head_sha": head_sha, "check_runs": flattened}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
