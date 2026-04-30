"""Constants for code_rules_gate.py per CODE_RULES centralized-config rule."""

from __future__ import annotations

MAX_VIOLATIONS_PER_CHECK: int = 3
EXPECTED_TUPLE_PAIR_LENGTH: int = 2

ALL_CODE_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".js", ".ts", ".tsx", ".jsx"}
)

ALL_LITERAL_KEYWORD_EXEMPTIONS: frozenset[str] = frozenset(
    {"true", "false", "none", "null"}
)

CONFIG_PATH_SEGMENT: str = "/config/"

TESTS_PATH_SEGMENT: str = "/tests/"

ALL_TEST_FILENAME_SUFFIXES: tuple[str, ...] = ("_test.py",)

ALL_TEST_FILENAME_GLOB_SUFFIXES: tuple[str, ...] = (
    ".test.",
    ".spec.",
)

TEST_CONFTEST_FILENAME: str = "conftest.py"

TEST_FILENAME_PREFIX: str = "test_"

MINIMUM_COLUMN_NAME_LENGTH_AFTER_FIRST_CHAR: int = 2

COLUMN_KEY_PATTERN_TEMPLATE: str = r"^[a-z][a-z0-9_]{{{minimum_length},}}$"

GIT_NAME_STATUS_ADDED_PREFIX: str = "A"

PYTHON_FILE_EXTENSION: str = ".py"
