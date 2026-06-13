#!/usr/bin/env python3
"""Blocking hook: a named subprocess-budget helper must account for every reachable subprocess timeout.

Fires when a Write/Edit produces a Python module that both:

  * defines a function whose name names a worst-case or budget total
    (contains ``worst_case``, ``_budget``, or ``budget_seconds``), and
  * passes ``timeout=`` (an integer literal or a module-level integer
    constant) to one or more ``subprocess.run`` calls,

but the budget total omits a distinct subprocess timeout value the module can
reach in one invocation. A budget helper that undercounts a reachable
subprocess timeout reports a wall-clock margin wider than the real one, so a
later change can silently cross the harness timeout while the named guard still
reads green.
"""

import ast
import json
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.subprocess_budget_completeness_constants import (  # noqa: E402
    ALL_BUDGET_NAME_MARKERS,
    SUBPROCESS_TIMEOUT_KEYWORD,
)
from hooks_constants.windows_rmtree_blocker_constants import (  # noqa: E402
    PYTHON_FILE_EXTENSION,
)


def is_python_target(file_path: str) -> bool:
    return file_path.endswith(PYTHON_FILE_EXTENSION)


def resolved_content(all_tool_input_fields: dict[str, object]) -> str:
    written_content = all_tool_input_fields.get("content")
    if isinstance(written_content, str):
        return written_content
    replacement_content = all_tool_input_fields.get("new_string")
    if isinstance(replacement_content, str):
        return replacement_content
    return ""


def integer_literal_value(node: ast.expr) -> int | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    ):
        return node.value
    return None


def resolved_integer_value(node: ast.expr, value_by_constant_name: dict[str, int]) -> int | None:
    literal_value = integer_literal_value(node)
    if literal_value is not None:
        return literal_value
    if isinstance(node, ast.Name):
        return value_by_constant_name.get(node.id)
    return None


def collect_subprocess_timeout_values(
    tree: ast.Module, value_by_constant_name: dict[str, int]
) -> set[int]:
    all_timeout_values: set[int] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Call):
            continue
        if not is_subprocess_run_call(each_node):
            continue
        for each_keyword in each_node.keywords:
            if each_keyword.arg != SUBPROCESS_TIMEOUT_KEYWORD:
                continue
            timeout_value = resolved_integer_value(each_keyword.value, value_by_constant_name)
            if timeout_value is not None:
                all_timeout_values.add(timeout_value)
    return all_timeout_values


def is_subprocess_run_call(call_node: ast.Call) -> bool:
    function_node = call_node.func
    if isinstance(function_node, ast.Attribute):
        return function_node.attr == "run" and _attribute_root_name(function_node) == "subprocess"
    return False


def _attribute_root_name(attribute_node: ast.Attribute) -> str | None:
    base_node = attribute_node.value
    if isinstance(base_node, ast.Name):
        return base_node.id
    return None


def summed_integer_literals(function_node: ast.FunctionDef) -> set[int]:
    all_summed_literals: set[int] = set()
    for each_node in ast.walk(function_node):
        literal_value = (
            integer_literal_value(each_node) if isinstance(each_node, ast.expr) else None
        )
        if literal_value is not None:
            all_summed_literals.add(literal_value)
    return all_summed_literals


def is_budget_function(function_node: ast.FunctionDef) -> bool:
    function_name = function_node.name.lower()
    return any(each_marker in function_name for each_marker in ALL_BUDGET_NAME_MARKERS)


def find_undercounted_budget(content: str) -> tuple[str, set[int]] | None:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    referenced_constants = collect_module_constant_values(tree)
    subprocess_timeout_values = collect_subprocess_timeout_values(tree, referenced_constants)
    if not subprocess_timeout_values:
        return None

    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.FunctionDef):
            continue
        if not is_budget_function(each_node):
            continue
        accounted_values = summed_integer_literals(each_node) | budget_named_constant_values(
            each_node, referenced_constants
        )
        omitted_values = subprocess_timeout_values - accounted_values
        if omitted_values:
            return each_node.name, omitted_values
    return None


def collect_module_constant_values(tree: ast.Module) -> dict[str, int]:
    value_by_constant_name: dict[str, int] = {}
    for each_node in tree.body:
        if isinstance(each_node, ast.Assign):
            assigned_value = integer_literal_value(each_node.value)
            if assigned_value is None:
                continue
            for each_target in each_node.targets:
                if isinstance(each_target, ast.Name):
                    value_by_constant_name[each_target.id] = assigned_value
        elif isinstance(each_node, ast.AnnAssign) and each_node.value is not None:
            annotated_value = integer_literal_value(each_node.value)
            if annotated_value is not None and isinstance(each_node.target, ast.Name):
                value_by_constant_name[each_node.target.id] = annotated_value
    return value_by_constant_name


def budget_named_constant_values(
    function_node: ast.FunctionDef, value_by_constant_name: dict[str, int]
) -> set[int]:
    all_referenced_values: set[int] = set()
    for each_node in ast.walk(function_node):
        if isinstance(each_node, ast.Name) and each_node.id in value_by_constant_name:
            all_referenced_values.add(value_by_constant_name[each_node.id])
    return all_referenced_values


def format_block_message(file_path: str, function_name: str, all_omitted_values: set[int]) -> str:
    omitted_text = ", ".join(str(each_value) for each_value in sorted(all_omitted_values))
    return (
        f"SUBPROCESS BUDGET INCOMPLETE: {function_name}() in {file_path} sums a subset of the "
        f"module's subprocess timeouts and omits timeout value(s) {omitted_text}s that one invocation "
        "can reach. A named worst-case/budget helper must account for every subprocess timeout reachable "
        "in a single invocation, so its reported margin against the harness timeout is real. Either add the "
        f"omitted timeout(s) to the modeled total, or rename the helper to name the phases it actually covers "
        "and document the residual full-invocation margin separately."
    )


def main() -> None:
    hook_input = read_hook_input_dictionary_from_stdin()
    if hook_input is None:
        sys.exit(0)

    raw_tool_input = hook_input.get("tool_input", {})
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path or not is_python_target(file_path):
        sys.exit(0)

    content = resolved_content(tool_input)
    if not content:
        sys.exit(0)

    undercounted_budget = find_undercounted_budget(content)
    if undercounted_budget is None:
        sys.exit(0)

    function_name, omitted_values = undercounted_budget
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": format_block_message(
                        file_path, function_name, omitted_values
                    ),
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
