"""Configuration constants for the pr-converge skill scripts.

Login/state constants identify reviewers and classify review states; reflow
constants control the SKILL.md reflow logic; regex/bugbot constants match
the literal phrasing the Cursor Bugbot reviewer emits.
"""

import re
from pathlib import Path

CURSOR_LOGIN_FILTER_SUBSTRING: str = "cursor"

COPILOT_LOGIN_FILTER_SUBSTRING: str = "copilot"

COPILOT_CLEAN_REVIEW_STATE: str = "APPROVED"

ALL_COPILOT_DIRTY_REVIEW_STATES: tuple[str, ...] = ("CHANGES_REQUESTED", "COMMENTED")

COPILOT_SOFT_DIRTY_REVIEW_STATE: str = "COMMENTED"

CLAUDE_LOGIN_FILTER_SUBSTRING: str = "claude"

CLAUDE_CLEAN_REVIEW_STATE: str = "APPROVED"

ALL_CLAUDE_DIRTY_REVIEW_STATES: tuple[str, ...] = ("CHANGES_REQUESTED", "COMMENTED")

CLAUDE_SOFT_DIRTY_REVIEW_STATE: str = "COMMENTED"

BUGBOT_DIRTY_BODY_REGEX: str = (
    r"Cursor Bugbot has reviewed your changes and found \d+ potential issue"
)


SKILL_REFLOW_MAXIMUM_WIDTH: int = 80

PR_CONVERGE_SKILL_PATH: Path = Path(__file__).resolve().parent.parent.parent / "SKILL.md"

MARKDOWN_CODE_FENCE_MARKER: str = "```"

YAML_FRONT_MATTER_DELIMITER: str = "---"

YAML_DESCRIPTION_PREFIX: str = "description: >-"

EXAMPLE_OPEN_TAG: str = "<example>"

EXAMPLE_CLOSE_TAG: str = "</example>"

BASH_FENCE_LANGUAGE: str = "bash"

BASH_LINE_CONTINUATION_SUFFIX: str = " \\"

BASH_CONTINUATION_INDENT: str = "  "

REFLOW_FRONT_MATTER_ERROR: str = "expected YAML front matter starting with ---"

ORDERED_MARKDOWN_LIST_PATTERN: re.Pattern[str] = re.compile(
    r"^(?P<leading_whitespace>\s*)(?P<marker>\d+\.\s)(?P<body>.*)$"
)

BULLET_MARKDOWN_LIST_PATTERN: re.Pattern[str] = re.compile(
    r"^(?P<leading_whitespace>\s*)(?P<marker>[-*]\s)(?P<body>.*)$"
)

UNFINISHED_MARKDOWN_LINK_TARGET_PATTERN: re.Pattern[str] = re.compile(r"\]\([^)]*$")

MARKDOWN_HEADING_PATTERN: re.Pattern[str] = re.compile(r"^#{1,6}\s+.+$")

MARKDOWN_REFERENCE_DEFINITION_PATTERN: re.Pattern[str] = re.compile(r"^\[[^\]]+\]:\s+\S+")

BASH_LINE_CONTINUATION_MARKER_WIDTH: int = 2

CODE_FENCE_MARKER_LENGTH: int = 3

BASH_MINIMUM_SEGMENT_WIDTH: int = 1

LONG_ROW_PREVIEW_LIMIT: int = 20
