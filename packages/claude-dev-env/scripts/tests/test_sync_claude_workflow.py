"""Tests for sync_claude_workflow: canonical comparison and repo filtering."""

from __future__ import annotations

import argparse
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


def test_should_exit_with_config_error_when_any_only_filter_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_repo_root = tmp_path / "fake-repo"
    workflow_directory = fake_repo_root / ".github" / "workflows"
    workflow_directory.mkdir(parents=True)
    (workflow_directory / "claude.yml").write_bytes(b"name: Claude Code\n")
    monkeypatch.setattr(sync_engine, "resolve_repo_root", lambda: fake_repo_root)
    monkeypatch.setattr(
        sync_engine,
        "parse_command_line_arguments",
        lambda: argparse.Namespace(
            dry_run=True,
            only=[sync_config.TARGET_REPOS[0], "typo/unknown-repo"],
        ),
    )

    exit_code = sync_engine.main()

    assert exit_code == sync_config.EXIT_CODE_CONFIG_ERROR
    captured_streams = capsys.readouterr()
    assert "typo/unknown-repo" in captured_streams.err


def test_should_raise_on_any_unknown_filter_even_with_valid_repos() -> None:
    first_target = sync_config.TARGET_REPOS[0]
    unknown_repository = "never-heard-of/this-repo"
    with pytest.raises(ValueError, match="never-heard-of/this-repo"):
        sync_engine.select_target_repos([first_target, unknown_repository])


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


def test_should_raise_when_stderr_contains_bare_404_without_http_prefix(
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


def test_should_return_none_when_gh_exit_is_nonstandard_but_stderr_reports_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_subprocess_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["gh", "api"],
            returncode=2,
            stdout="",
            stderr="gh: HTTP 404 Not Found",
        )

    monkeypatch.setattr(sync_engine.subprocess, "run", fake_subprocess_run)
    assert sync_engine.fetch_remote_file_metadata("owner/repo") is None


@pytest.mark.parametrize(
    ("remote_metadata", "expect_sha_key"),
    [
        (None, False),
        ({"sha": "abc123", "content_base64": ""}, True),
    ],
)
def test_should_include_sha_only_when_updating_existing_file(
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


def test_should_prefix_push_failures_with_push_label(
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


def test_should_skip_subprocess_and_print_action_in_dry_run_mode(
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


def test_should_return_clean_failure_when_gh_stdout_is_not_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_subprocess_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["gh", "api"],
            returncode=0,
            stdout="not json at all",
            stderr="",
        )

    monkeypatch.setattr(sync_engine.subprocess, "run", fake_subprocess_run)

    sync_succeeded = sync_engine.sync_single_repo(
        repository_full_name="owner/repo",
        canonical_bytes=b"canonical",
        dry_run=True,
    )

    assert sync_succeeded is False
    captured_streams = capsys.readouterr()
    assert "FAILED (fetch):" in captured_streams.err


def test_should_raise_runtime_error_when_gh_stdout_cannot_be_decoded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_subprocess_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["gh", "api"],
            returncode=0,
            stdout="<<< not json >>>",
            stderr="",
        )

    monkeypatch.setattr(sync_engine.subprocess, "run", fake_subprocess_run)

    with pytest.raises(RuntimeError):
        sync_engine.fetch_remote_file_metadata("owner/repo")


def test_should_raise_runtime_error_when_api_payload_lacks_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rate_limit_body = json.dumps({"message": "API rate limit exceeded"})

    def fake_subprocess_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["gh", "api"],
            returncode=0,
            stdout=rate_limit_body,
            stderr="",
        )

    monkeypatch.setattr(sync_engine.subprocess, "run", fake_subprocess_run)

    with pytest.raises(RuntimeError) as exception_info:
        sync_engine.fetch_remote_file_metadata("owner/repo")
    assert "shape" in str(exception_info.value) or "unexpected" in str(exception_info.value).lower()


def test_should_raise_runtime_error_when_api_payload_is_not_a_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory_listing_body = json.dumps([{"name": "claude.yml", "type": "file"}])

    def fake_subprocess_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["gh", "api"],
            returncode=0,
            stdout=directory_listing_body,
            stderr="",
        )

    monkeypatch.setattr(sync_engine.subprocess, "run", fake_subprocess_run)

    with pytest.raises(RuntimeError):
        sync_engine.fetch_remote_file_metadata("owner/repo")


def test_should_exit_with_config_error_when_all_only_filters_are_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_repo_root = tmp_path / "fake-repo"
    workflow_directory = fake_repo_root / ".github" / "workflows"
    workflow_directory.mkdir(parents=True)
    (workflow_directory / "claude.yml").write_bytes(b"name: Claude Code\n")
    monkeypatch.setattr(sync_engine, "resolve_repo_root", lambda: fake_repo_root)
    monkeypatch.setattr(
        sync_engine,
        "parse_command_line_arguments",
        lambda: argparse.Namespace(dry_run=True, only=["typo/name", "also/unknown"]),
    )

    exit_code = sync_engine.main()

    assert exit_code == sync_config.EXIT_CODE_CONFIG_ERROR
    captured_streams = capsys.readouterr()
    assert "typo/name" in captured_streams.err
    assert "also/unknown" in captured_streams.err


def test_should_exit_with_config_error_when_canonical_file_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty_repo_root = tmp_path / "empty-repo"
    empty_repo_root.mkdir()
    monkeypatch.setattr(sync_engine, "resolve_repo_root", lambda: empty_repo_root)
    monkeypatch.setattr(
        sync_engine,
        "parse_command_line_arguments",
        lambda: argparse.Namespace(dry_run=True, only=[sync_config.TARGET_REPOS[0]]),
    )

    exit_code = sync_engine.main()

    assert exit_code == sync_config.EXIT_CODE_CONFIG_ERROR
    captured_streams = capsys.readouterr()
    assert "Canonical workflow missing" in captured_streams.err
