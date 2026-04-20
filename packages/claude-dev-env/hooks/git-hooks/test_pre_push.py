from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import pre_push
import config


ALL_ZEROS_OBJECT_NAME: str = "0" * 40


def test_resolve_base_reference_uses_remote_object_when_non_zero() -> None:
    stdin_text = (
        f"refs/heads/feature abcdef1234567890 refs/heads/feature 1111222233334444\n"
    )

    base_reference = pre_push.resolve_base_reference_from_stdin(stdin_text)

    assert base_reference == "1111222233334444"


def test_resolve_base_reference_falls_back_when_remote_is_all_zeros() -> None:
    stdin_text = f"refs/heads/feature abcdef1234567890 refs/heads/feature {ALL_ZEROS_OBJECT_NAME}\n"

    base_reference = pre_push.resolve_base_reference_from_stdin(stdin_text)

    assert base_reference == pre_push.DEFAULT_REMOTE_BASE_REFERENCE


def test_resolve_base_reference_falls_back_when_stdin_empty() -> None:
    base_reference = pre_push.resolve_base_reference_from_stdin("")

    assert base_reference == pre_push.DEFAULT_REMOTE_BASE_REFERENCE


def test_resolve_base_reference_prefers_first_non_zero_remote_object_among_many() -> (
    None
):
    stdin_text = (
        f"refs/heads/new_branch abcdef refs/heads/new_branch {ALL_ZEROS_OBJECT_NAME}\n"
        f"refs/heads/existing 111111 refs/heads/existing 2222222222\n"
    )

    base_reference = pre_push.resolve_base_reference_from_stdin(stdin_text)

    assert base_reference == "2222222222"


def test_main_exits_zero_when_gate_script_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CODE_RULES_GATE_PATH",
        str(tmp_path / "does_not_exist.py"),
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    exit_code = pre_push.main()

    assert exit_code == 0


def test_main_invokes_gate_with_resolved_base_reference(
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
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO("refs/heads/feature abcdef refs/heads/feature 9999888877776666\n"),
    )

    exit_code = pre_push.main()

    assert exit_code == 0
    assert recorded_arguments_path.exists(), (
        f"recording gate did not write to {recorded_arguments_path}"
    )
    recorded_arguments = recorded_arguments_path.read_text(
        encoding="utf-8"
    ).splitlines()
    assert recorded_arguments == ["--base", "9999888877776666"]


def test_main_propagates_blocking_exit_code_from_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocking_gate_script_path = tmp_path / "blocking_gate.py"
    blocking_gate_script_path.write_text(
        "import sys\nsys.exit(1)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(blocking_gate_script_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    exit_code = pre_push.main()

    assert exit_code == 1


def test_main_propagates_infrastructure_failure_exit_code_from_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    infrastructure_failure_gate_path = tmp_path / "infrastructure_failure_gate.py"
    infrastructure_failure_gate_path.write_text(
        "import sys\nsys.exit(2)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(infrastructure_failure_gate_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    exit_code = pre_push.main()

    assert exit_code == 2


def test_main_exits_two_when_stdin_raises_ioerror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate_path = tmp_path / "gate.py"
    gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(gate_path))

    class RaisingStdin:
        def read(self) -> str:
            raise IOError("broken pipe")

    monkeypatch.setattr(sys, "stdin", RaisingStdin())

    exit_code = pre_push.main()

    assert exit_code == config.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE


def test_main_exits_two_when_invoke_gate_raises_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate_path = tmp_path / "gate.py"
    gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(gate_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    def raising_run(*args: object, **kwargs: object) -> object:
        raise OSError("no such file")

    monkeypatch.setattr(__import__("subprocess"), "run", raising_run)

    exit_code = pre_push.main()

    assert exit_code == config.GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE


def test_resolve_base_reference_emits_warning_for_malformed_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    malformed_stdin_text = "only_one_field\n"

    pre_push.resolve_base_reference_from_stdin(malformed_stdin_text)

    captured = capsys.readouterr()
    assert "malformed" in captured.err
