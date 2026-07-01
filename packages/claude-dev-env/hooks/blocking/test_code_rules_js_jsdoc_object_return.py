"""Tests for check_js_jsdoc_object_return_schemaless_agent.

The check catches the JS/.mjs slice of Category O6
docstring-prose-vs-implementation drift: a ``function`` declaration whose JSDoc
declares ``@returns {Promise<object>}`` while a ``return`` branch calls a
schema-less ``convergeAgent(...)`` / ``agent(...)``. A schema-less agent call
resolves to a string transcript, not a structured object, so the object return
type misdescribes that branch. The drift this reproduces is PR #807:
``runGitTask``'s ``prefetch-main`` branch and ``runCodeEditorTask``'s
``hardening-commit`` branch each return a schema-less agent call under a
``@returns {Promise<object>}`` JSDoc.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_module_spec = importlib.util.spec_from_file_location(
    "code_rules_imports_logging",
    _HOOK_DIRECTORY / "code_rules_imports_logging.py",
)
assert _module_spec is not None
assert _module_spec.loader is not None
_imports_logging_module = importlib.util.module_from_spec(_module_spec)
_module_spec.loader.exec_module(_imports_logging_module)

check_js_jsdoc_object_return_schemaless_agent = (
    _imports_logging_module.check_js_jsdoc_object_return_schemaless_agent
)

_MJS_PATH = "skills/autoconverge/workflow/converge.mjs"


def _schemaless_object_return_source() -> str:
    return (
        "/**\n"
        " * Spawn a git-utility agent for a specific task.\n"
        " * @returns {Promise<object>} the structured output\n"
        " */\n"
        "function runGitTask(task) {\n"
        "  if (task === 'resolve-head') {\n"
        "    return convergeAgent(`Print the HEAD sha.`, "
        "{ label: 'git', schema: HEAD_SCHEMA, agentType: 'Explore' })\n"
        "  }\n"
        "  if (task === 'prefetch-main') {\n"
        "    return convergeAgent(`Fetch origin main.`, "
        "{ label: 'git', agentType: 'Explore' })\n"
        "  }\n"
        "  return convergeAgent(`Report conflicts.`, "
        "{ label: 'git', schema: MERGE_SCHEMA, agentType: 'Explore' })\n"
        "}\n"
    )


def test_flags_object_return_over_schemaless_agent_branch() -> None:
    issues = check_js_jsdoc_object_return_schemaless_agent(
        _schemaless_object_return_source(), _MJS_PATH
    )
    assert len(issues) == 1
    assert "runGitTask" in issues[0]


def test_ignores_function_where_every_agent_return_has_schema() -> None:
    source = (
        "/**\n"
        " * @returns {Promise<object>} the structured output\n"
        " */\n"
        "function runFixerTask(task) {\n"
        "  if (task === 'commit') {\n"
        "    return convergeAgent(`Commit.`, "
        "{ label: 'fix', schema: FIX_SCHEMA, agentType: 'clean-coder' })\n"
        "  }\n"
        "  return convergeAgent(`Recover.`, "
        "{ label: 'fix', schema: EDIT_SCHEMA, agentType: 'clean-coder' })\n"
        "}\n"
    )
    assert check_js_jsdoc_object_return_schemaless_agent(source, _MJS_PATH) == []


def test_ignores_string_return_type_jsdoc() -> None:
    source = (
        "/**\n"
        " * @returns {Promise<string>} the transcript\n"
        " */\n"
        "function runPrefetch() {\n"
        "  return convergeAgent(`Fetch origin main.`, "
        "{ label: 'git', agentType: 'Explore' })\n"
        "}\n"
    )
    assert check_js_jsdoc_object_return_schemaless_agent(source, _MJS_PATH) == []


def test_ignores_union_return_type_jsdoc() -> None:
    source = (
        "/**\n"
        " * @returns {Promise<object|string>} the object or the transcript\n"
        " */\n"
        "function runMixed(task) {\n"
        "  if (task === 'x') {\n"
        "    return convergeAgent(`X.`, { label: 'git', schema: X_SCHEMA })\n"
        "  }\n"
        "  return convergeAgent(`Y.`, { label: 'git', agentType: 'Explore' })\n"
        "}\n"
    )
    assert check_js_jsdoc_object_return_schemaless_agent(source, _MJS_PATH) == []


def test_prose_schema_in_prompt_string_does_not_count_as_options_schema() -> None:
    source = (
        "/**\n"
        " * @returns {Promise<object>} the structured output\n"
        " */\n"
        "function runPromptSchema() {\n"
        "  return convergeAgent(`Return the schema field. Do not attach a schema here.`, "
        "{ label: 'git', agentType: 'Explore' })\n"
        "}\n"
    )
    issues = check_js_jsdoc_object_return_schemaless_agent(source, _MJS_PATH)
    assert len(issues) == 1
    assert "runPromptSchema" in issues[0]


def test_ignores_spread_options_that_may_supply_schema() -> None:
    source = (
        "/**\n"
        " * @returns {Promise<object>} the structured output\n"
        " */\n"
        "function runSpread() {\n"
        "  return convergeAgent(`Go.`, { ...baseOptions, label: 'git' })\n"
        "}\n"
    )
    assert check_js_jsdoc_object_return_schemaless_agent(source, _MJS_PATH) == []


def test_ignores_non_javascript_file() -> None:
    assert (
        check_js_jsdoc_object_return_schemaless_agent(
            _schemaless_object_return_source(), "hooks/blocking/some_module.py"
        )
        == []
    )


def _one_drifting_function(index: int) -> str:
    return (
        "/**\n"
        " * @returns {Promise<object>} the structured output\n"
        " */\n"
        "function drifting" + str(index) + "() {\n"
        "  return convergeAgent(`Go.`, { label: 'git', agentType: 'Explore' })\n"
        "}\n"
    )


def test_caps_issue_count_at_module_limit() -> None:
    maximum_issues = _imports_logging_module.MAX_JS_JSDOC_OBJECT_RETURN_ISSUES
    source = "".join(
        _one_drifting_function(each_index)
        for each_index in range(maximum_issues + 3)
    )
    issues = check_js_jsdoc_object_return_schemaless_agent(source, _MJS_PATH)
    assert len(issues) == maximum_issues
