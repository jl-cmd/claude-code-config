from __future__ import annotations

import sys
from pathlib import Path

import pytest


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import gate_utils


def test_resolve_gate_script_path_uses_override_env_var_when_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_path = tmp_path / "override_gate.py"
    override_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(override_path))

    resolved_path = gate_utils.resolve_gate_script_path()

    assert resolved_path == override_path


def test_resolve_gate_script_path_defaults_to_claude_home_when_env_var_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODE_RULES_GATE_PATH", raising=False)
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path))

    resolved_path = gate_utils.resolve_gate_script_path()

    expected_path = (
        tmp_path / "skills" / "bugteam" / "scripts" / "bugteam_code_rules_gate.py"
    )
    assert resolved_path == expected_path


def test_resolve_gate_script_path_falls_back_to_home_dot_claude_when_no_env_vars(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODE_RULES_GATE_PATH", raising=False)
    monkeypatch.delenv("CLAUDE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    resolved_path = gate_utils.resolve_gate_script_path()

    expected_path = (
        tmp_path
        / ".claude"
        / "skills"
        / "bugteam"
        / "scripts"
        / "bugteam_code_rules_gate.py"
    )
    assert resolved_path == expected_path


def test_resolve_gate_script_path_resolves_relative_override_to_absolute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODE_RULES_GATE_PATH", "relative/gate.py")

    resolved_path = gate_utils.resolve_gate_script_path()

    assert resolved_path.is_absolute()


def test_is_safe_regular_file_rejects_sibling_of_override_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Override allow-list must not permit sibling files in the same directory."""
    override_gate = tmp_path / "gate.py"
    override_gate.write_text("", encoding="utf-8")
    sibling_script = tmp_path / "attacker_script.py"
    sibling_script.write_text("", encoding="utf-8")
    monkeypatch.delenv("CLAUDE_HOME", raising=False)
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(override_gate))
    monkeypatch.setattr(
        Path,
        "home",
        staticmethod(lambda: tmp_path / "unrelated_home"),
    )

    is_safe = gate_utils.is_safe_regular_file(sibling_script)

    assert not is_safe


def test_is_safe_regular_file_accepts_exact_override_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_gate = tmp_path / "gate.py"
    override_gate.write_text("", encoding="utf-8")
    monkeypatch.delenv("CLAUDE_HOME", raising=False)
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(override_gate))
    monkeypatch.setattr(
        Path,
        "home",
        staticmethod(lambda: tmp_path / "unrelated_home"),
    )

    is_safe = gate_utils.is_safe_regular_file(override_gate)

    assert is_safe
