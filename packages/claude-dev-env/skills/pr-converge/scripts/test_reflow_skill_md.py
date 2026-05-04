"""Tests for reflow_skill_md.

Covers:
- wrap_long_bash_line returns unchanged when indent leaves zero/negative width
- wrap_long_bash_fence_lines handles deeply-indented bash content safely
- structural string literals are imported from config, not inline
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent


def _load_module(module_name: str) -> ModuleType:
    if str(_SCRIPTS_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIRECTORY))
    module_path = _SCRIPTS_DIRECTORY / "reflow_skill_md.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reflow_module = _load_module("reflow_skill_md")


def test_should_load_when_other_config_module_is_cached() -> None:
    sys.modules["config"] = ModuleType("config")
    loaded_module = _load_module("reflow_skill_md_with_cached_config")
    assert loaded_module.SKILL_REFLOW_MAXIMUM_WIDTH == 80


def test_should_preserve_pr_converge_state_json_path_in_yaml_description() -> None:
    lines = [
        "  Multi-PR runs persist traffic in",
        "  `<TMPDIR>/pr-converge-<session_id>/state.json` per Multi-PR",
        "  orchestration model.",
        "---",
    ]
    all_reflowed_lines, next_index = reflow_module.reflow_yaml_description_block(lines, 0)
    reflowed_description = " ".join(each_line.strip() for each_line in all_reflowed_lines)

    assert next_index == len(lines)
    assert "`<TMPDIR>/pr-converge-<session_id>/state.json`" in reflowed_description
    assert "`<TMPDIR>/pr-converge-<session_id>/state.json>`" not in reflowed_description


def test_wrap_long_bash_line_returns_unchanged_when_indent_exceeds_max_width() -> None:
    """When indentation >= SKILL_REFLOW_MAXIMUM_WIDTH, return line as-is."""
    deep_indent = " " * 85
    long_line = deep_indent + "echo hello world this is a long command"
    all_result_lines = reflow_module.wrap_long_bash_line(long_line)
    assert all_result_lines == [long_line]


def test_wrap_long_bash_line_returns_unchanged_when_indent_equals_max_width() -> None:
    """When indentation == SKILL_REFLOW_MAXIMUM_WIDTH, return line as-is."""
    deep_indent = " " * 80
    long_line = deep_indent + "echo hello"
    all_result_lines = reflow_module.wrap_long_bash_line(long_line)
    assert all_result_lines == [long_line]


def test_wrap_long_bash_fence_lines_handles_deeply_indented_bash() -> None:
    """Full pipeline does not hang on bash fence with extreme indentation."""
    deep_indent = " " * 90
    all_input_lines = [
        "```bash",
        deep_indent + "some_command --flag value --other long argument text here",
        "```",
    ]
    all_result_lines = reflow_module.wrap_long_bash_fence_lines(all_input_lines)
    assert len(all_result_lines) == 3
    assert all_result_lines[0] == "```bash"
    assert all_result_lines[2] == "```"
    assert all_result_lines[1] == all_input_lines[1]


def test_is_new_logical_line_recognizes_fence_via_constant() -> None:
    """Code fence detection uses the imported constant marker."""
    assert reflow_module.is_new_logical_line("```bash") is True
    assert reflow_module.is_new_logical_line("```") is True


def test_reflow_structural_line_recognizes_example_tags_via_constant() -> None:
    """Example tag detection uses imported constant markers."""
    assert reflow_module.reflow_structural_line("<example>", "<example>") == ["<example>"]
    close_result = reflow_module.reflow_structural_line("</example>", "</example>")
    assert close_result == ["</example>"]


def test_reflow_structural_line_recognizes_yaml_delimiter_via_constant() -> None:
    """YAML delimiter detection uses imported constant."""
    assert reflow_module.reflow_structural_line("---", "---") == ["---"]


def test_reflow_structural_line_preserves_reference_definitions() -> None:
    long_reference_definition = (
        "[path-a]: "
        "https://example.com/this/reference/definition/path/is/long/enough/to/exceed/the/wrap/limit"
    )
    all_result_lines = reflow_module.reflow_merged_line(long_reference_definition)
    assert all_result_lines == [long_reference_definition]
