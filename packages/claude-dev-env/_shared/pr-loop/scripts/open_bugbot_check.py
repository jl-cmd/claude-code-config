"""Open the Cursor Bugbot check-run details for a pull request.

Prints the check-run html_url for browser navigation and lists any annotations
(issues found) from the Bugbot analysis.
"""

import argparse
import json
import sys
from pathlib import Path

sys.modules.pop("config", None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.bugbot_check_constants import (
    BUGBOT_CHECK_NAME,
    CHECK_RUNS_JQ_FILTER,
    CHECK_RUNS_PATH_TEMPLATE,
    CHECK_RUN_ANNOTATIONS_PATH_TEMPLATE,
)
from gh_util import resolve_head_sha, run_gh


def _find_latest_bugbot_run(
    owner: str, repo: str, sha: str
) -> dict[str, object] | None:
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
) -> list[dict[str, object]] | None:
    endpoint = CHECK_RUN_ANNOTATIONS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, check_run_id=check_run_id
    )
    gh_result = run_gh(["gh", "api", endpoint])
    if gh_result.returncode != 0:
        print("Failed to fetch check-run annotations", file=sys.stderr)
        return None
    try:
        return json.loads(gh_result.stdout)
    except json.JSONDecodeError:
        print("Failed to parse annotations response", file=sys.stderr)
        return None


def main(all_arguments: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Show Cursor Bugbot check-run details and annotations for a PR."
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed = parser.parse_args(all_arguments)

    head_sha = resolve_head_sha(parsed.owner, parsed.repo, parsed.number)
    if head_sha is None:
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
    raise SystemExit(main(sys.argv[1:]))
