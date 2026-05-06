"""Constants for review posting and verification logic."""

EXIT_OK: int = 0
EXIT_NO_REVIEW: int = 1
EXIT_WRONG_COMMIT: int = 2
EXIT_DUPLICATE_REVIEW: int = 3

REVIEWS_PATH_TEMPLATE: str = "/repos/{owner}/{repo}/pulls/{number}/reviews?per_page=100"

LOOP_AUDIT_HEADER_TEMPLATE: str = "## Loop {loop_number} Audit"
BUGTEAM_LOOP_HEADER_TEMPLATE: str = "## /bugteam loop {loop_number} "

REVIEW_POST_ENDPOINT_TEMPLATE: str = (
    "/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
)
COMMENT_POST_ENDPOINT_TEMPLATE: str = (
    "/repos/{owner}/{repo}/pulls/{pull_number}/comments"
)

GH_FIELD_BODY_AT_PREFIX: str = "body=@"

REVIEW_EVENT_COMMENT: str = "COMMENT"
REVIEW_COMMENTS_SIDE: str = "RIGHT"
