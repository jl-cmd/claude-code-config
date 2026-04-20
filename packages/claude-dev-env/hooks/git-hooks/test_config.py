from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import config


def test_staged_scope_argument_is_git_staged_flag() -> None:
    assert config.STAGED_SCOPE_ARGUMENT == "--staged"


def test_base_reference_argument_is_gate_base_flag() -> None:
    assert config.BASE_REFERENCE_ARGUMENT == "--base"


def test_default_remote_base_reference_targets_origin_head() -> None:
    assert config.DEFAULT_REMOTE_BASE_REFERENCE == "origin/HEAD"


def test_all_zeros_object_name_character_is_zero_digit() -> None:
    assert config.ALL_ZEROS_OBJECT_NAME_CHARACTER == "0"


def test_stdin_line_field_count_matches_pre_push_protocol() -> None:
    assert config.STDIN_LINE_FIELD_COUNT == 4


def test_stdin_remote_object_field_index_points_to_fourth_field() -> None:
    assert config.STDIN_REMOTE_OBJECT_FIELD_INDEX == 3


def test_gate_path_override_env_var_name() -> None:
    assert config.GATE_PATH_OVERRIDE_ENV_VAR == "CODE_RULES_GATE_PATH"


def test_claude_home_env_var_name() -> None:
    assert config.CLAUDE_HOME_ENV_VAR == "CLAUDE_HOME"


def test_claude_home_default_subdirectory_is_dot_claude() -> None:
    assert config.CLAUDE_HOME_DEFAULT_SUBDIRECTORY == ".claude"


def test_gate_script_relative_path_locates_bugteam_gate() -> None:
    assert config.GATE_SCRIPT_RELATIVE_PATH == (
        "skills",
        "bugteam",
        "scripts",
        "bugteam_code_rules_gate.py",
    )
