"""Tests for the Cursor Agents AutoHotkey pacer."""

from __future__ import annotations

from pathlib import Path


def _script_text() -> str:
    return (Path(__file__).resolve().parent / "cursor-agents-continue.ahk").read_text(
        encoding="utf-8"
    )


def _function_body(function_name: str, next_marker: str) -> str:
    script_text = _script_text()
    function_start = script_text.index(function_name)
    function_end = script_text.index(next_marker, function_start)
    return script_text[function_start:function_end]


def test_should_fallback_when_pwsh_is_unavailable() -> None:
    terminate_body = _function_body(
        "terminate_other_script_instances() {",
        "\n}\n\nrun_stop_script_with_shell",
    )
    helper_body = _function_body(
        "run_stop_script_with_shell(shell_name, stop_script) {",
        "\n}\n\nterminate_other_script_instances()",
    )

    assert 'run_stop_script_with_shell("pwsh", stop_script)' in terminate_body
    assert 'run_stop_script_with_shell("powershell.exe", stop_script)' in terminate_body
    assert "try {" in helper_body
    assert "catch" in helper_body
    assert "RunWait(shell_name stop_command_arguments" in helper_body
