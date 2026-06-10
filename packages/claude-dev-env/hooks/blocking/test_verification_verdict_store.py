"""Behavioral tests for verification_verdict_store against real git repos."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verification_verdict_store import (    branch_surface_manifest,
    is_docs_only_diff,
    load_valid_verdict,
    manifest_sha256,
    resolve_merge_base,
    resolve_repo_root,
    stripped_ast_dump,
    verdict_path_for_repo,
    write_verdict,
)

BEHAVIORAL_MODULE = '"""Module doc."""\n\n\ndef add(left: int, right: int) -> int:\n    """Add two ints."""\n    return left + right\n'


def run(repo_dir: Path, *git_args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_dir), *git_args],
        check=True,
        capture_output=True,
        text=True,
    )


def build_cloned_repo(tmp_path: Path) -> Path:
    """Create an upstream repo plus a clone whose origin/main resolves.

    Both repos point ``core.hooksPath`` at an empty directory so the
    developer machine's global git hooks never fire inside the fixtures.
    """
    empty_hooks_dir = tmp_path / "git_hooks_empty"
    empty_hooks_dir.mkdir(exist_ok=True)
    upstream_dir = tmp_path / "upstream"
    upstream_dir.mkdir()
    run(upstream_dir, "init", "-b", "main")
    run(upstream_dir, "config", "user.email", "test@example.com")
    run(upstream_dir, "config", "user.name", "Test")
    run(upstream_dir, "config", "core.hooksPath", str(empty_hooks_dir))
    (upstream_dir / "module.py").write_text(BEHAVIORAL_MODULE, encoding="utf-8")
    (upstream_dir / "README.md").write_text("# readme\n", encoding="utf-8")
    run(upstream_dir, "add", "-A")
    run(upstream_dir, "commit", "-m", "base")
    clone_dir = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", str(upstream_dir), str(clone_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    run(clone_dir, "config", "user.email", "test@example.com")
    run(clone_dir, "config", "user.name", "Test")
    run(clone_dir, "config", "core.hooksPath", str(empty_hooks_dir))
    run(clone_dir, "checkout", "-b", "feature")
    return clone_dir


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.setenv("HOME", str(home_dir))
    return home_dir


class TestStrippedAstDump:
    def test_should_match_when_only_docstrings_differ(self) -> None:
        reworded = BEHAVIORAL_MODULE.replace("Add two ints.", "Sum a pair.")
        assert stripped_ast_dump(BEHAVIORAL_MODULE) == stripped_ast_dump(reworded)

    def test_should_match_when_only_comments_differ(self) -> None:
        commented = BEHAVIORAL_MODULE.replace(
            "    return left + right", "    # fast path\n    return left + right"
        )
        assert stripped_ast_dump(BEHAVIORAL_MODULE) == stripped_ast_dump(commented)

    def test_should_differ_when_behavior_changes(self) -> None:
        changed = BEHAVIORAL_MODULE.replace("left + right", "left - right")
        assert stripped_ast_dump(BEHAVIORAL_MODULE) != stripped_ast_dump(changed)

    def test_should_return_none_for_unparseable_source(self) -> None:
        assert stripped_ast_dump("def broken(:\n") is None


class TestBranchDiffUntrackedFiles:
    def test_should_change_hash_when_untracked_file_appears(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        baseline_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        (clone_dir / "unstaged_module.py").write_text("VALUE = 1\n", encoding="utf-8")
        untracked_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        assert untracked_hash != baseline_hash

    def test_should_change_hash_when_untracked_content_changes(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        (clone_dir / "unstaged_module.py").write_text("VALUE = 1\n", encoding="utf-8")
        first_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        (clone_dir / "unstaged_module.py").write_text("VALUE = 2\n", encoding="utf-8")
        second_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        assert second_hash != first_hash

    def test_should_keep_hash_stable_across_staging_and_commit(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        (clone_dir / "unstaged_module.py").write_text("VALUE = 1\n", encoding="utf-8")
        untracked_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        run(clone_dir, "add", "-A")
        staged_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        run(clone_dir, "commit", "-m", "slice")
        committed_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        assert untracked_hash == staged_hash == committed_hash

    def test_should_skip_tooling_state_directories(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        baseline_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        scratch_dir = clone_dir / ".claude" / "worktrees"
        scratch_dir.mkdir(parents=True)
        (scratch_dir / "scratch_module.py").write_text("VALUE = 1\n", encoding="utf-8")
        assert manifest_sha256(branch_surface_manifest(repo_root, merge_base)) == baseline_hash
        assert is_docs_only_diff(repo_root, merge_base) is True


class TestDocsOnlyDiff:
    def test_should_exempt_markdown_and_docstring_changes(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        (clone_dir / "README.md").write_text("# reworded\n", encoding="utf-8")
        reworded = BEHAVIORAL_MODULE.replace("Add two ints.", "Sum a pair.")
        (clone_dir / "module.py").write_text(reworded, encoding="utf-8")
        repo_root = resolve_repo_root(str(clone_dir))
        assert repo_root is not None
        merge_base = resolve_merge_base(repo_root)
        assert merge_base is not None
        assert is_docs_only_diff(repo_root, merge_base) is True

    def test_should_gate_behavioral_python_change(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        changed = BEHAVIORAL_MODULE.replace("left + right", "left - right")
        (clone_dir / "module.py").write_text(changed, encoding="utf-8")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        assert is_docs_only_diff(repo_root, merge_base) is False

    def test_should_gate_new_python_file(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        (clone_dir / "new_module.py").write_text("VALUE = 1\n", encoding="utf-8")
        run(clone_dir, "add", "-A")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        assert is_docs_only_diff(repo_root, merge_base) is False

    def test_should_gate_untracked_python_file(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        (clone_dir / "unstaged_module.py").write_text("VALUE = 1\n", encoding="utf-8")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        assert is_docs_only_diff(repo_root, merge_base) is False

    def test_should_exempt_untracked_markdown_file(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        (clone_dir / "NOTES.md").write_text("# notes\n", encoding="utf-8")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        assert is_docs_only_diff(repo_root, merge_base) is True

    def test_should_gate_python_file_renamed_to_docs_extension(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        run(clone_dir, "mv", "module.py", "module.md")
        run(clone_dir, "commit", "-m", "disguise module as docs")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        assert is_docs_only_diff(repo_root, merge_base) is False

    def test_should_exempt_pure_docs_rename(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        run(clone_dir, "mv", "README.md", "DOCS.md")
        run(clone_dir, "commit", "-m", "rename docs")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        assert is_docs_only_diff(repo_root, merge_base) is True

    def test_should_gate_non_python_code_file(self, tmp_path: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        (clone_dir / "script.ps1").write_text("Write-Output hi\n", encoding="utf-8")
        run(clone_dir, "add", "-A")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        assert is_docs_only_diff(repo_root, merge_base) is False


class TestVerdictRoundTrip:
    def test_should_load_only_matching_passing_verdict(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        changed = BEHAVIORAL_MODULE.replace("left + right", "left * right")
        (clone_dir / "module.py").write_text(changed, encoding="utf-8")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        live_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        verdict_file = write_verdict(repo_root, live_hash, True, [], "agent-1")
        assert verdict_file == verdict_path_for_repo(repo_root)
        assert verdict_file.is_relative_to(isolated_home)
        assert load_valid_verdict(repo_root, live_hash) is not None
        assert load_valid_verdict(repo_root, "0" * 64) is None

    def test_should_reject_failing_verdict(self, tmp_path: Path, isolated_home: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        live_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        write_verdict(repo_root, live_hash, False, [{"check": "tests"}], "agent-2")
        assert load_valid_verdict(repo_root, live_hash) is None

    def test_should_invalidate_after_further_edit(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        changed = BEHAVIORAL_MODULE.replace("left + right", "left * right")
        (clone_dir / "module.py").write_text(changed, encoding="utf-8")
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        verified_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        write_verdict(repo_root, verified_hash, True, [], "agent-3")
        (clone_dir / "module.py").write_text(changed + "\nEXTRA = 2\n", encoding="utf-8")
        post_edit_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        assert post_edit_hash != verified_hash
        assert load_valid_verdict(repo_root, post_edit_hash) is None
