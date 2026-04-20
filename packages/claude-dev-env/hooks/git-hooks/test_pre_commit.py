from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import pre_commit


def make_gate_script_returning(exit_code: int, target_path: Path) -> Path:
    target_path.write_text(
        f"import sys\nsys.exit({exit_code})\n",
        encoding="utf-8",
    )
    return target_path


@pytest.fixture()
def fake_gate_script_blocking(tmp_path: Path) -> Path:
    return make_gate_script_returning(1, tmp_path / "fake_gate_blocking.py")


@pytest.fixture()
def fake_gate_script_passing(tmp_path: Path) -> Path:
    return make_gate_script_returning(0, tmp_path / "fake_gate_passing.py")


def test_resolve_gate_script_path_uses_override_env_var_when_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_path = tmp_path / "override_gate.py"
    override_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(override_path))

    resolved_path = pre_commit.resolve_gate_script_path()

    assert resolved_path == override_path


def test_resolve_gate_script_path_defaults_to_claude_home_skills_location(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODE_RULES_GATE_PATH", raising=False)
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path))

    resolved_path = pre_commit.resolve_gate_script_path()

    expected_path = (
        tmp_path / "skills" / "bugteam" / "scripts" / "bugteam_code_rules_gate.py"
    )
    assert resolved_path == expected_path


def test_main_exits_zero_when_gate_script_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CODE_RULES_GATE_PATH",
        str(tmp_path / "does_not_exist.py"),
    )

    exit_code = pre_commit.main()

    assert exit_code == 0


def test_main_propagates_blocking_exit_code_from_gate(
    fake_gate_script_blocking: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(fake_gate_script_blocking))

    exit_code = pre_commit.main()

    assert exit_code == 1


def test_main_propagates_passing_exit_code_from_gate(
    fake_gate_script_passing: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(fake_gate_script_passing))

    exit_code = pre_commit.main()

    assert exit_code == 0


def test_main_invokes_gate_with_staged_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_arguments_path = tmp_path / "recorded_arguments.txt"
    recording_gate_script_path = tmp_path / "recording_gate.py"
    recording_gate_script_path.write_text(
        "import sys, pathlib\n"
        f'pathlib.Path(r"{recorded_arguments_path}").write_text('
        "'\\n'.join(sys.argv[1:]), encoding='utf-8')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(recording_gate_script_path))

    exit_code = pre_commit.main()

    assert exit_code == 0
    recorded_arguments = recorded_arguments_path.read_text(
        encoding="utf-8"
    ).splitlines()
    assert recorded_arguments == ["--staged"]
