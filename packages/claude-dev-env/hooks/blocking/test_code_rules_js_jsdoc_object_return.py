"""Tests for check_js_jsdoc_object_return_schema_coverage.

The check catches a JS/.mjs slice of Category O6 docstring-prose-vs-implementation
drift: a function whose JSDoc declares ``@returns {Promise<object>}`` while a
branch returns an agent-spawn call that omits the ``schema`` option, so that
branch resolves to a transcript string rather than the promised object. The
drift this reproduces is PR #807: ``runGitTask``'s ``prefetch-main`` branch and
``runCodeEditorTask``'s ``hardening-commit`` branch each call ``convergeAgent``
without a schema, so ``agent()`` returns a string, yet both JSDocs claim
``Promise<object>``.
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

check_js_jsdoc_object_return_schema_coverage = (
    _imports_logging_module.check_js_jsdoc_object_return_schema_coverage
)

_MJS_PATH = "skills/autoconverge/workflow/converge.mjs"


def _drifted_git_task_source() -> str:
    return (
        "/**\n"
        " * Spawn a fresh git-utility Explore agent for a specific task.\n"
        " * @param {string} task the short task name\n"
        " * @returns {Promise<object>} the structured output\n"
        " */\n"
        "function runGitTask(task, head) {\n"
        "  if (task === 'resolve-head') {\n"
        "    return convergeAgent(\n"
        "      `Print the HEAD SHA of ${prCoordinates}.`,\n"
        "      { label: 'git-utility', phase: 'Converge', schema: HEAD_SCHEMA, agentType: 'Explore' },\n"
        "    )\n"
        "  }\n"
        "  if (task === 'prefetch-main') {\n"
        "    return convergeAgent(\n"
        "      `Refresh the base ref for ${prCoordinates}.`,\n"
        "      { label: 'git-utility', phase: 'Converge', agentType: 'Explore' },\n"
        "    )\n"
        "  }\n"
        "  return convergeAgent(\n"
        "    `Report whether ${prCoordinates} has merge conflicts.`,\n"
        "    { label: 'git-utility', phase: 'Converge', schema: MERGE_CONFLICT_SCHEMA, agentType: 'Explore' },\n"
        "  )\n"
        "}\n"
    )


def _aligned_git_task_source() -> str:
    return _drifted_git_task_source().replace(
        "@returns {Promise<object>} the structured output",
        "@returns {Promise<object|string>} the structured output or a transcript",
    )


def should_flag_promise_object_jsdoc_with_schemaless_return_branch() -> None:
    issues = check_js_jsdoc_object_return_schema_coverage(_drifted_git_task_source(), _MJS_PATH)
    assert len(issues) == 1
    assert "runGitTask" in issues[0]
    assert "convergeAgent" in issues[0]
    assert "schema" in issues[0]


def should_pass_when_returns_type_covers_the_string_case() -> None:
    issues = check_js_jsdoc_object_return_schema_coverage(_aligned_git_task_source(), _MJS_PATH)
    assert issues == []


def should_pass_when_every_returned_call_passes_a_schema() -> None:
    source = _drifted_git_task_source().replace(
        "      { label: 'git-utility', phase: 'Converge', agentType: 'Explore' },\n",
        "      { label: 'git-utility', phase: 'Converge', schema: HEAD_SCHEMA, agentType: 'Explore' },\n",
    )
    issues = check_js_jsdoc_object_return_schema_coverage(source, _MJS_PATH)
    assert issues == []


def should_not_flag_when_no_returned_call_ever_passes_a_schema() -> None:
    source = (
        "/**\n"
        " * Build a dashboard from the profile already in scope.\n"
        " * @returns {Promise<object>} the dashboard\n"
        " */\n"
        "function buildDashboard(profile) {\n"
        "  if (profile.isEmpty) {\n"
        "    return renderPlaceholder({ label: 'empty' })\n"
        "  }\n"
        "  return renderDashboard({ name: profile.name, plan: profile.plan })\n"
        "}\n"
    )
    issues = check_js_jsdoc_object_return_schema_coverage(source, _MJS_PATH)
    assert issues == []


def should_ignore_string_return_jsdoc() -> None:
    source = _drifted_git_task_source().replace(
        "@returns {Promise<object>} the structured output",
        "@returns {Promise<string>} the transcript",
    )
    issues = check_js_jsdoc_object_return_schema_coverage(source, _MJS_PATH)
    assert issues == []


def should_treat_schema_word_inside_prompt_string_as_schemaless() -> None:
    source = (
        "/**\n"
        " * Spawn an editor agent for a task.\n"
        " * @returns {Promise<object>} the structured output\n"
        " */\n"
        "function runEditorTask(task) {\n"
        "  if (task === 'fix-edit') {\n"
        "    return convergeAgent(`Fix it.`, { label, schema: EDIT_SCHEMA })\n"
        "  }\n"
        "  return convergeAgent(`Honor the schema: pass a body-file.`, { label })\n"
        "}\n"
    )
    issues = check_js_jsdoc_object_return_schema_coverage(source, _MJS_PATH)
    assert len(issues) == 1
    assert "runEditorTask" in issues[0]


def should_ignore_python_files() -> None:
    issues = check_js_jsdoc_object_return_schema_coverage(
        _drifted_git_task_source(), "skills/autoconverge/workflow/converge.py"
    )
    assert issues == []


def should_skip_test_files() -> None:
    issues = check_js_jsdoc_object_return_schema_coverage(
        _drifted_git_task_source(), "skills/autoconverge/workflow/converge.test.mjs"
    )
    assert issues == []
