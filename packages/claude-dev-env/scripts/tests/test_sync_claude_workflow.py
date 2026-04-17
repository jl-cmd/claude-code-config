"""Tests for sync_claude_workflow: canonical comparison and repo filtering."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sync_claude_workflow import config as sync_config
from sync_claude_workflow import engine as sync_engine


def test_should_treat_missing_remote_file_as_mismatch() -> None:
    canonical_bytes = b"name: Claude Code\n"
    assert sync_engine.remote_matches_canonical(None, canonical_bytes) is False


def test_should_match_when_remote_base64_decodes_to_canonical_bytes() -> None:
    canonical_bytes = b"name: Claude Code\n"
    remote_metadata = {
        "sha": "abc123",
        "content_base64": base64.b64encode(canonical_bytes).decode("ascii"),
    }
    assert (
        sync_engine.remote_matches_canonical(remote_metadata, canonical_bytes) is True
    )


def test_should_detect_mismatch_when_remote_content_differs() -> None:
    canonical_bytes = b"name: Claude Code\n"
    drifted_remote_bytes = b"name: Drifted Copy\n"
    remote_metadata = {
        "sha": "abc123",
        "content_base64": base64.b64encode(drifted_remote_bytes).decode("ascii"),
    }
    assert (
        sync_engine.remote_matches_canonical(remote_metadata, canonical_bytes) is False
    )


def test_should_read_canonical_workflow_from_repo(tmp_path: Path) -> None:
    fake_repo_root = tmp_path / "fake-repo"
    workflow_directory = fake_repo_root / ".github" / "workflows"
    workflow_directory.mkdir(parents=True)
    canonical_contents = b"name: Claude Code\non: {}\n"
    (workflow_directory / "claude.yml").write_bytes(canonical_contents)

    actual_bytes = sync_engine.read_canonical_workflow_bytes(fake_repo_root)
    assert actual_bytes == canonical_contents


def test_should_return_all_repos_when_filter_is_empty() -> None:
    assert sync_engine.select_target_repos([]) == sync_config.TARGET_REPOS


def test_should_select_only_repos_listed_in_filter() -> None:
    first_target = sync_config.TARGET_REPOS[0]
    second_target = sync_config.TARGET_REPOS[1]
    selected = sync_engine.select_target_repos([first_target, second_target])
    assert selected == (first_target, second_target)


def test_should_drop_unknown_repos_from_filter(capsys: pytest.CaptureFixture[str]) -> None:
    first_target = sync_config.TARGET_REPOS[0]
    unknown_repository = "never-heard-of/this-repo"
    selected = sync_engine.select_target_repos([first_target, unknown_repository])
    assert selected == (first_target,)
    captured_streams = capsys.readouterr()
    assert unknown_repository in captured_streams.err
