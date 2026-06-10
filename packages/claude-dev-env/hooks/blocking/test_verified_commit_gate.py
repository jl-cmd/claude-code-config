"""Behavioral tests for verified_commit_gate against real git repos."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_verification_verdict_store import (    BEHAVIORAL_MODULE,
    build_cloned_repo,
    isolated_home,
)
from verification_verdict_store import (    branch_surface_manifest,
    manifest_sha256,
    resolve_merge_base,
    resolve_repo_root,
    write_verdict,
)
from verified_commit_gate import (    deny_reason_for_directory,
    gated_repo_directories,
    main,
)

_ = isolated_home


def run_main_with_payload(payload: dict) -> str:
    captured = io.StringIO()
    sys.stdin = io.StringIO(json.dumps(payload))
    try:
        with redirect_stdout(captured):
            main()
    finally:
        sys.stdin = sys.__stdin__
    return captured.getvalue()


class TestGatedRepoDirectories:
    def test_should_detect_plain_commit_with_session_cwd(self) -> None:
        assert gated_repo_directories('git commit -m "x"', "/work") == ["/work"]

    def test_should_detect_dash_c_repo_path(self) -> None:
        directories = gated_repo_directories('git -C "C:\\repos\\demo" commit -m "x"', "/work")
        assert directories == ["C:\\repos\\demo"]

    def test_should_detect_push_inside_pwsh_wrapper(self) -> None:
        wrapped = 'pwsh -NoProfile -Command "git push origin feature"'
        assert gated_repo_directories(wrapped, "/work") == ["/work"]

    def test_should_ignore_non_landing_git_commands(self) -> None:
        assert gated_repo_directories("git log --oneline -5", "/work") == []
        assert gated_repo_directories("git status", "/work") == []

    def test_should_ignore_gated_verbs_outside_subcommand_position(self) -> None:
        assert gated_repo_directories("git stash push", "/work") == []
        assert gated_repo_directories("git log --grep commit", "/work") == []

    def test_should_detect_gated_verb_case_insensitively(self) -> None:
        assert gated_repo_directories('Git Commit -m "x"', "/work") == ["/work"]

    def test_should_skip_config_flag_value_before_subcommand(self) -> None:
        assert gated_repo_directories("git -c user.name=x commit -m y", "/work") == ["/work"]

    def test_should_detect_each_segment_of_compound_command(self) -> None:
        compound = "git add -A; git commit -m x && git push origin feature"
        assert gated_repo_directories(compound, "/work") == ["/work", "/work"]


class TestDenyReason:
    def test_should_allow_when_no_repo_resolves(self, tmp_path: Path) -> None:
        missing_dir = tmp_path / "missing" / "deeper"
        assert deny_reason_for_directory(str(missing_dir)) is None

    def test_should_allow_docs_only_branch(self, tmp_path: Path, isolated_home: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        (clone_dir / "README.md").write_text("# reworded\n", encoding="utf-8")
        assert deny_reason_for_directory(str(clone_dir)) is None

    def test_should_deny_behavioral_diff_without_verdict(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        changed = BEHAVIORAL_MODULE.replace("left + right", "left - right")
        (clone_dir / "module.py").write_text(changed, encoding="utf-8")
        deny_reason = deny_reason_for_directory(str(clone_dir))
        assert deny_reason is not None
        assert "VERIFIED_COMMIT_GATE" in deny_reason

    def test_should_allow_behavioral_diff_with_minted_verdict(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        changed = BEHAVIORAL_MODULE.replace("left + right", "left - right")
        (clone_dir / "module.py").write_text(changed, encoding="utf-8")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        live_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        write_verdict(repo_root, live_hash, True, [], "agent-9")
        assert deny_reason_for_directory(str(clone_dir)) is None

    def test_should_deny_again_after_post_verdict_edit(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        changed = BEHAVIORAL_MODULE.replace("left + right", "left - right")
        (clone_dir / "module.py").write_text(changed, encoding="utf-8")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        live_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        write_verdict(repo_root, live_hash, True, [], "agent-9")
        (clone_dir / "module.py").write_text(changed + "\nEXTRA = 3\n", encoding="utf-8")
        post_edit_deny_reason = deny_reason_for_directory(str(clone_dir))
        assert "VERIFIED_COMMIT_GATE" in (post_edit_deny_reason or "")

    def test_should_deny_after_post_verdict_untracked_file(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        changed = BEHAVIORAL_MODULE.replace("left + right", "left - right")
        (clone_dir / "module.py").write_text(changed, encoding="utf-8")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        live_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        write_verdict(repo_root, live_hash, True, [], "agent-9")
        (clone_dir / "unstaged_module.py").write_text("VALUE = 1\n", encoding="utf-8")
        untracked_deny_reason = deny_reason_for_directory(str(clone_dir))
        assert "VERIFIED_COMMIT_GATE" in (untracked_deny_reason or "")


class TestMainEndToEnd:
    def test_should_emit_deny_payload_for_unverified_commit(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        changed = BEHAVIORAL_MODULE.replace("left + right", "left - right")
        (clone_dir / "module.py").write_text(changed, encoding="utf-8")
        gate_output = run_main_with_payload(
            {
                "tool_name": "PowerShell",
                "tool_input": {"command": 'git commit -m "feat: x"'},
                "cwd": str(clone_dir),
            }
        )
        decision = json.loads(gate_output)
        assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_should_stay_silent_for_other_tools_and_commands(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        assert (
            run_main_with_payload(
                {
                    "tool_name": "Read",
                    "tool_input": {"command": "git commit"},
                    "cwd": str(clone_dir),
                }
            )
            == ""
        )
        assert (
            run_main_with_payload(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "git status"},
                    "cwd": str(clone_dir),
                }
            )
            == ""
        )
