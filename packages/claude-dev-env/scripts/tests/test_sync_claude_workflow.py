"""Tests for sync_claude_workflow: canonical comparison and repo filtering."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

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


def test_should_return_none_when_gh_api_reports_http_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_subprocess_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["gh", "api"],
            returncode=1,
            stdout="",
            stderr="gh: Not Found (HTTP 404)",
        )

    monkeypatch.setattr(sync_engine.subprocess, "run", fake_subprocess_run)
    assert sync_engine.fetch_remote_file_metadata("owner/repo") is None


def test_should_raise_when_stderr_mentions_404_in_unrelated_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_subprocess_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["gh", "api"],
            returncode=1,
            stdout="",
            stderr="gh: rate limited (details: 404 in URL path)",
        )

    monkeypatch.setattr(sync_engine.subprocess, "run", fake_subprocess_run)
    with pytest.raises(RuntimeError):
        sync_engine.fetch_remote_file_metadata("owner/repo")


@pytest.mark.parametrize(
    ("remote_metadata", "expect_sha_key"),
    [
        (None, False),
        ({"sha": "abc123", "content_base64": ""}, True),
    ],
)
def test_push_canonical_to_repo_includes_sha_only_when_updating_existing_file(
    monkeypatch: pytest.MonkeyPatch,
    remote_metadata: dict[str, str] | None,
    expect_sha_key: bool,
) -> None:
    subprocess_spy = MagicMock(
        return_value=subprocess.CompletedProcess(
            args=["gh", "api"],
            returncode=0,
            stdout="",
            stderr="",
        )
    )
    monkeypatch.setattr(sync_engine.subprocess, "run", subprocess_spy)

    sync_engine.push_canonical_to_repo(
        repository_full_name="owner/repo",
        canonical_bytes=b"name: Claude Code\n",
        remote_metadata=remote_metadata,
        dry_run=False,
    )

    assert subprocess_spy.call_count == 1
    request_body_json = subprocess_spy.call_args.kwargs["input"]
    request_body = json.loads(request_body_json)
    assert ("sha" in request_body) is expect_sha_key


def test_push_canonical_to_repo_prefixes_failures_with_push_label(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_subprocess_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["gh", "api"],
            returncode=1,
            stdout="",
            stderr="remote rejected the write",
        )

    monkeypatch.setattr(sync_engine.subprocess, "run", fake_subprocess_run)

    push_succeeded = sync_engine.push_canonical_to_repo(
        repository_full_name="owner/repo",
        canonical_bytes=b"name: Claude Code\n",
        remote_metadata=None,
        dry_run=False,
    )

    assert push_succeeded is False
    captured_streams = capsys.readouterr()
    assert "FAILED (push):" in captured_streams.err


def test_push_canonical_to_repo_in_dry_run_mode_skips_subprocess_and_prints_action(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    subprocess_spy = MagicMock()
    monkeypatch.setattr(sync_engine.subprocess, "run", subprocess_spy)

    create_succeeded = sync_engine.push_canonical_to_repo(
        repository_full_name="owner/repo",
        canonical_bytes=b"name: Claude Code\n",
        remote_metadata=None,
        dry_run=True,
    )
    update_succeeded = sync_engine.push_canonical_to_repo(
        repository_full_name="owner/repo",
        canonical_bytes=b"name: Claude Code\n",
        remote_metadata={"sha": "abc123", "content_base64": ""},
        dry_run=True,
    )

    assert create_succeeded is True
    assert update_succeeded is True
    assert subprocess_spy.call_count == 0
    captured_streams = capsys.readouterr()
    assert "CREATE" in captured_streams.out
    assert "UPDATE" in captured_streams.out
