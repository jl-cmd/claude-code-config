"""Show Cursor Bugbot check-run details and annotations for a pull request.

Prints the check-run html_url for browser navigation, status, conclusion,
the analysis pipeline summary, and any annotations (issues found).
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
    CHECK_RUN_ANNOTATIONS_PATH_TEMPLATE,
    PR_NUMBER_ARG_FLAG,
    PR_NUMBER_ARG_HELP,
    PR_OWNER_ARG_FLAG,
    PR_OWNER_ARG_HELP,
    PR_REPO_ARG_FLAG,
    PR_REPO_ARG_HELP,
)

from resolve_pr_head import resolve_pr_head



def _find_latest_bugbot_run(
    owner: str, repo: str, sha: str
) -> dict[str, object] | None:
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
        return None
    try:
        all_check_runs = json.loads(completed.stdout)
    except json.JSONDecodeError:
        print("Failed to parse check-runs response", file=sys.stderr)
        return None
    if not isinstance(all_check_runs, list):
        return None
    bugbot_runs = [
        each_run
        for each_run in all_check_runs
        if isinstance(each_run, dict) and each_run.get("name") == BUGBOT_CHECK_NAME
    ]
    if not bugbot_runs:
        return None
    bugbot_runs.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return bugbot_runs[0]


def _fetch_annotations(
    owner: str, repo: str, check_run_id: int
) -> list[dict[str, object]]:
    endpoint = CHECK_RUN_ANNOTATIONS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, check_run_id=check_run_id
    )
    completed = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        return []
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        PR_NUMBER_ARG_FLAG, required=True, type=int, help=PR_NUMBER_ARG_HELP
    )
    parser.add_argument(PR_OWNER_ARG_FLAG, required=True, help=PR_OWNER_ARG_HELP)
    parser.add_argument(PR_REPO_ARG_FLAG, required=True, help=PR_REPO_ARG_HELP)
    parsed = parser.parse_args()

    try:
        head_sha = resolve_pr_head(owner=parsed.owner, repo=parsed.repo, number=parsed.number)
    except subprocess.CalledProcessError:
        print("Failed to resolve PR head SHA", file=sys.stderr)
        return 1

    bugbot_run = _find_latest_bugbot_run(parsed.owner, parsed.repo, head_sha)
    if bugbot_run is None:
        print(
            f"No Cursor Bugbot check run found on {head_sha[:7]}",
            file=sys.stderr,
        )
        return 1

    check_run_id = bugbot_run.get("id")
    html_url = bugbot_run.get("html_url", "")
    check_output = bugbot_run.get("output", {})
    if isinstance(check_output, dict):
        annotations_count = check_output.get("annotations_count", 0)
        summary = check_output.get("summary", "")
    else:
        annotations_count = 0
        summary = ""

    print(f"html_url: {html_url}")
    print(f"status: {bugbot_run.get('status')}")
    print(f"conclusion: {bugbot_run.get('conclusion')}")
    print(f"annotations_count: {annotations_count}")
    print()
    print(summary)

    if isinstance(check_run_id, int) and annotations_count > 0:
        print()
        annotations = _fetch_annotations(parsed.owner, parsed.repo, check_run_id)
        if annotations:
            for each_annotation in annotations:
                print(
                    f"- {each_annotation.get('path', '')}:"
                    f"{each_annotation.get('start_line', '')}"
                    f" [{each_annotation.get('annotation_level', '')}] "
                    f"{each_annotation.get('message', '')}"
                )

    return 0


if __name__ == "__main__":
    sys.exit(main())
