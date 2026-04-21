"""Tests for setup_project_paths — one-time bootstrap script."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import setup_project_paths as setup


class TestFinalSegmentFilter:
    def test_retains_dot_git_directory(self) -> None:
        all_paths = ["C:\\Projects\\my-repo\\.git"]
        retained = setup.filter_to_git_roots(all_paths)
        assert retained == ["C:\\Projects\\my-repo"]

    def test_rejects_dot_gitignore(self) -> None:
        all_paths = ["C:\\Projects\\my-repo\\.gitignore"]
        retained = setup.filter_to_git_roots(all_paths)
        assert retained == []

    def test_rejects_dot_github(self) -> None:
        all_paths = ["C:\\Projects\\my-repo\\.github"]
        retained = setup.filter_to_git_roots(all_paths)
        assert retained == []

    def test_accepts_dot_git_with_forward_slashes(self) -> None:
        all_paths = ["C:/Projects/my-repo/.git"]
        retained = setup.filter_to_git_roots(all_paths)
        assert retained == ["C:/Projects/my-repo"]

    def test_retains_multiple_valid_git_roots(self) -> None:
        all_paths = [
            "C:\\Projects\\alpha\\.git",
            "D:\\Work\\beta\\.git",
        ]
        retained = setup.filter_to_git_roots(all_paths)
        assert "C:\\Projects\\alpha" in retained
        assert "D:\\Work\\beta" in retained

    def test_rejects_dot_git_attributes(self) -> None:
        all_paths = ["C:\\Projects\\my-repo\\.gitattributes"]
        retained = setup.filter_to_git_roots(all_paths)
        assert retained == []


class TestExclusionFilter:
    def test_drops_path_with_temp_segment(self) -> None:
        all_candidates = ["C:\\temp\\my-repo"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_drops_path_with_tmp_segment(self) -> None:
        all_candidates = ["C:\\tmp\\my-repo"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_drops_path_with_worktree_segment(self) -> None:
        all_candidates = ["C:\\Projects\\main\\worktree\\feature"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_drops_path_with_node_modules_segment(self) -> None:
        all_candidates = ["C:\\Projects\\app\\node_modules\\pkg"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_drops_path_with_dot_cache_segment(self) -> None:
        all_candidates = ["C:\\Users\\jon\\.cache\\build"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_drops_path_with_recycle_bin_segment(self) -> None:
        all_candidates = ["C:\\$Recycle.Bin\\S-1-5\\my-repo"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == []

    def test_preserves_path_with_template_segment(self) -> None:
        all_candidates = ["C:\\Projects\\template"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == ["C:\\Projects\\template"]

    def test_preserves_legitimate_project_path(self) -> None:
        all_candidates = ["Y:\\Projects\\my-app"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == ["Y:\\Projects\\my-app"]

    def test_whole_segment_match_does_not_drop_template(self) -> None:
        all_candidates = ["C:\\Projects\\my-templates\\repo"]
        filtered = setup.apply_exclusion_filter(all_candidates)
        assert filtered == ["C:\\Projects\\my-templates\\repo"]


class TestMergeRegistries:
    def test_merge_preserves_pre_existing_entries(self) -> None:
        existing_registry = {
            "_meta": {"schema_version": 1, "last_scan": "2026-01-01T00:00:00Z"},
            "old-repo": "C:\\Old\\old-repo",
        }
        new_name_by_path = {"new-repo": "D:\\New\\new-repo"}
        merged = setup.merge_registries(existing_registry, new_name_by_path)
        assert merged["old-repo"] == "C:\\Old\\old-repo"
        assert merged["new-repo"] == "D:\\New\\new-repo"

    def test_merge_updates_meta_last_scan(self) -> None:
        existing_registry: dict = {}
        new_name_by_path = {"alpha": "C:\\alpha"}
        merged = setup.merge_registries(existing_registry, new_name_by_path)
        assert "_meta" in merged
        assert "last_scan" in merged["_meta"]

    def test_merge_new_entry_wins_on_name_collision(self) -> None:
        existing_registry = {"my-repo": "C:\\Old\\path"}
        new_name_by_path = {"my-repo": "D:\\New\\path"}
        merged = setup.merge_registries(existing_registry, new_name_by_path)
        assert merged["my-repo"] == "D:\\New\\path"


class TestAtomicWrite:
    def test_write_creates_file_with_correct_content(self, tmp_path: Path) -> None:
        target_file = tmp_path / "project-paths.json"
        registry_to_write = {"_meta": {"schema_version": 1}, "repo": "C:\\repo"}
        setup.write_registry_atomically(registry_to_write, target_file)
        written_content = json.loads(target_file.read_text(encoding="utf-8"))
        assert written_content["repo"] == "C:\\repo"

    def test_write_leaves_no_temp_file_on_success(self, tmp_path: Path) -> None:
        target_file = tmp_path / "project-paths.json"
        registry_to_write = {"_meta": {"schema_version": 1}}
        setup.write_registry_atomically(registry_to_write, target_file)
        all_files = list(tmp_path.iterdir())
        assert all_files == [target_file]

    def test_write_refuses_higher_schema_version(self, tmp_path: Path) -> None:
        target_file = tmp_path / "project-paths.json"
        target_file.write_text(
            json.dumps({"_meta": {"schema_version": 99}}), encoding="utf-8"
        )
        with pytest.raises(setup.SchemaMismatchError):
            setup.write_registry_atomically(
                {"_meta": {"schema_version": 1}}, target_file
            )


class TestUserRejection:
    def test_user_rejection_at_final_prompt_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        target_file = tmp_path / "project-paths.json"
        assert not target_file.exists()
        with patch("builtins.input", return_value="no"):
            setup.prompt_and_write(
                name_by_path={"my-repo": "C:\\my-repo"},
                save_path=target_file,
            )
        assert not target_file.exists()
