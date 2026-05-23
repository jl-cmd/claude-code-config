"""Behavior tests: the generated FIX spawn prompt embeds the fix-push gate.

Runs the real emit_fix_prompt against a real findings JSON file (no mocks) and
asserts the rendered XML carries the pre-push gate step and the Category-K
enumerable-class carve-out, so a fix teammate reading the prompt body always
sees the gate-before-push instruction even when the PreToolUse hook does not
fire inside the subagent.
"""

import importlib.util
import json
import pathlib
import sys

_SCRIPTS_DIR = pathlib.Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "build_fix_prompt", _SCRIPTS_DIR / "build_fix_prompt.py"
)
assert _spec is not None
assert _spec.loader is not None
build_fix_prompt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_fix_prompt)


def _emit_prompt(tmp_path: pathlib.Path) -> str:
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps([{"category": "K", "file": "a.py", "line": 1, "title": "x"}]),
        encoding="utf-8",
    )
    return build_fix_prompt.emit_fix_prompt(
        owner="jl-cmd",
        repo="claude-code-config",
        pr_number=484,
        loop=1,
        head_ref="feat/converge-fix-gate",
        base_ref="worktree-feat-process-leak-tightening-batch",
        worktree_path=tmp_path,
        findings_json_path=findings_path,
    )


def test_fix_prompt_contains_pre_push_gate_step(tmp_path: pathlib.Path) -> None:
    xml_output = _emit_prompt(tmp_path)
    assert "fix-push gate" in xml_output
    assert "code_rules_gate.py" in xml_output
    assert ".gate.json" in xml_output


def test_fix_prompt_gate_step_precedes_commit_and_push(tmp_path: pathlib.Path) -> None:
    xml_output = _emit_prompt(tmp_path)
    gate_index = xml_output.index("fix-push gate")
    commit_index = xml_output.index("Stage and commit")
    push_index = xml_output.index("Push the commit")
    assert gate_index < commit_index < push_index


def test_fix_prompt_contains_category_k_carveout(tmp_path: pathlib.Path) -> None:
    xml_output = _emit_prompt(tmp_path)
    assert "enumerable class" in xml_output
