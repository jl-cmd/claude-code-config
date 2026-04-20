from __future__ import annotations

import sys
from pathlib import Path

import pytest


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import pre_commit
import gate_utils


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
    assert recorded_arguments_path.exists(), (
        f"recording gate did not write to {recorded_arguments_path}"
    )
    recorded_arguments = recorded_arguments_path.read_text(
        encoding="utf-8"
    ).splitlines()
    assert recorded_arguments == ["--staged"]


def test_main_exits_two_when_invoke_gate_raises_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_gate_path = tmp_path / "gate.py"
    existing_gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(existing_gate_path))

    original_run = __import__("subprocess").run

    def raising_run(*args: object, **kwargs: object) -> object:
        raise OSError("no such file")

    monkeypatch.setattr(__import__("subprocess"), "run", raising_run)

    exit_code = pre_commit.main()

    assert exit_code == 2


def test_main_emits_stderr_warning_when_gate_script_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(
        "CODE_RULES_GATE_PATH",
        str(tmp_path / "does_not_exist.py"),
    )

    exit_code = pre_commit.main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "gate script not found" in captured.err
