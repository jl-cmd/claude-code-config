"""Tests for setup_project_paths — one-time bootstrap script."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
_HOOKS_DIR = _SCRIPTS_DIR.parent / "hooks"
for each_sys_path_entry in (str(_SCRIPTS_DIR), str(_HOOKS_DIR)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

import setup_project_paths as setup
from hook_config.setup_project_paths_constants import ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS


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
        new_path_by_name = {"new-repo": "D:\\New\\new-repo"}
        merged = setup.merge_registries(existing_registry, new_path_by_name)
        assert merged["old-repo"] == "C:\\Old\\old-repo"
        assert merged["new-repo"] == "D:\\New\\new-repo"

    def test_merge_updates_meta_last_scan(self) -> None:
        existing_registry: dict = {}
        new_path_by_name = {"alpha": "C:\\alpha"}
        merged = setup.merge_registries(existing_registry, new_path_by_name)
        assert "_meta" in merged
        assert "last_scan" in merged["_meta"]

    def test_merge_new_entry_wins_on_name_collision(self) -> None:
        existing_registry = {"my-repo": "C:\\Old\\path"}
        new_path_by_name = {"my-repo": "D:\\New\\path"}
        merged = setup.merge_registries(existing_registry, new_path_by_name)
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


class TestEsExeQueryArguments:
    def test_arguments_do_not_include_name_flag(self) -> None:
        assert "-name" not in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS

    def test_arguments_include_folders_only_flag(self) -> None:
        assert "/ad" in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS

    def test_arguments_include_git_folder_query(self) -> None:
        assert "folder:.git" in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS

    def test_filter_to_git_roots_processes_full_absolute_paths(self) -> None:
        all_raw_paths = [
            "C:\\Projects\\my-repo\\.git",
            "D:\\Work\\other-repo\\.git",
        ]
        all_roots = setup.filter_to_git_roots(all_raw_paths)
        assert "C:\\Projects\\my-repo" in all_roots
        assert "D:\\Work\\other-repo" in all_roots


class TestUserRejection:
    def test_user_rejection_at_final_prompt_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        target_file = tmp_path / "project-paths.json"
        assert not target_file.exists()
        with patch("builtins.input", return_value="no"):
            setup.prompt_and_write(
                path_by_name={"my-repo": "C:\\my-repo"},
                save_path=target_file,
            )
        assert not target_file.exists()


class TestDuplicateLeafName:
    def test_duplicate_leaf_name_keeps_first_seen_entry(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        all_roots = sorted(["Y:\\A\\foo", "Y:\\B\\foo"])
        path_by_name = setup._build_path_by_name_from_roots(all_roots)
        assert len(path_by_name) == 1
        assert path_by_name["foo"] == "Y:\\A\\foo"

    def test_duplicate_leaf_name_prints_collision_warning(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        all_roots = sorted(["Y:\\A\\foo", "Y:\\B\\foo"])
        setup._build_path_by_name_from_roots(all_roots)
        captured = capsys.readouterr()
        assert "Duplicate leaf name 'foo'" in captured.out
        assert "Y:\\A\\foo" in captured.out
        assert "Y:\\B\\foo" in captured.out


class TestMapNamingConvention:
    def test_merge_registries_signature_uses_path_by_name(self) -> None:
        """Pin PR #230 round 3 rename: X_by_Y means X indexed by Y.

        The map's keys are repo names and values are paths, so the correct
        name is `path_by_name` (path indexed by name). The old inverted
        name `name_by_path` must not reappear.
        """
        import inspect

        merge_signature = inspect.signature(setup.merge_registries)
        assert "new_path_by_name" in merge_signature.parameters
        assert "new_name_by_path" not in merge_signature.parameters

    def test_build_helper_is_named_path_by_name(self) -> None:
        assert hasattr(setup, "_build_path_by_name_from_roots")
        assert not hasattr(setup, "_build_name_by_path_from_roots")
