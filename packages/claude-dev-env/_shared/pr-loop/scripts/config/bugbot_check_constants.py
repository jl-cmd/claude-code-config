"""Constants for bugbot check-run scripts."""

BUGBOT_CHECK_NAME: str = "Cursor Bugbot"
CHECK_RUNS_PATH_TEMPLATE: str = "/repos/{owner}/{repo}/commits/{sha}/check-runs"
CHECK_RUNS_JQ_FILTER: str = ".check_runs"
CHECK_RUN_ANNOTATIONS_PATH_TEMPLATE: str = (
    "/repos/{owner}/{repo}/check-runs/{check_run_id}/annotations"
)
PR_ENDPOINT_TEMPLATE: str = "/repos/{owner}/{repo}/pulls/{pull_number}"
PR_HEAD_SHA_JQ_FILTER: str = ".head.sha"
