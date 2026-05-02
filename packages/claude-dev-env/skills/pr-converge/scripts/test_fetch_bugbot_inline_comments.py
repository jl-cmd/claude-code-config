"""Tests for fetch_bugbot_inline_comments.

Covers:
- gh command uses --paginate --slurp on the comments endpoint
- only cursor[bot] inline comments are returned
- comments not anchored to the requested commit are filtered out
- multi-page responses are flattened correctly
- subprocess errors propagate
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _load_module() -> ModuleType:
    module_path = Path(__file__).parent / "fetch_bugbot_inline_comments.py"
    spec = importlib.util.spec_from_file_location(
        "fetch_bugbot_inline_comments", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch_bugbot_inline_comments_module = _load_module()


def _completed(stdout: str) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = 0
    return process


def test_should_invoke_gh_with_paginate_slurp_against_comments_endpoint() -> None:
    pages_payload = json.dumps([[]])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        fetch_bugbot_inline_comments_module.fetch_bugbot_inline_comments(
            owner="acme", repo="widget", number=42, current_head="abc123"
        )
    invoked_argv = mock_run.call_args[0][0]
    assert invoked_argv[0] == "gh"
    assert invoked_argv[1] == "api"
    assert "repos/acme/widget/pulls/42/comments?per_page=100" in invoked_argv[2]
    assert "--paginate" in invoked_argv
    assert "--slurp" in invoked_argv


def test_should_filter_to_cursor_bot_only() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 100,
                    "user": {"login": "copilot-pull-request-reviewer[bot]"},
                    "commit_id": "abc123",
                    "body": "copilot finding",
                    "path": "x.py",
                    "line": 5,
                },
                {
                    "id": 101,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "abc123",
                    "body": "bugbot finding",
                    "path": "x.py",
                    "line": 6,
                },
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_inline_comments = (
            fetch_bugbot_inline_comments_module.fetch_bugbot_inline_comments(
                owner="acme", repo="widget", number=42, current_head="abc123"
            )
        )
    assert len(all_inline_comments) == 1
    assert all_inline_comments[0]["comment_id"] == 101


def test_should_filter_out_comments_not_on_current_head() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 200,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "old_sha",
                    "body": "stale finding",
                    "path": "x.py",
                    "line": 5,
                },
                {
                    "id": 201,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "current_sha",
                    "body": "fresh finding",
                    "path": "x.py",
                    "line": 6,
                },
            ]
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_inline_comments = (
            fetch_bugbot_inline_comments_module.fetch_bugbot_inline_comments(
                owner="acme", repo="widget", number=42, current_head="current_sha"
            )
        )
    assert len(all_inline_comments) == 1
    assert all_inline_comments[0]["comment_id"] == 201


def test_should_flatten_across_pages() -> None:
    pages_payload = json.dumps(
        [
            [
                {
                    "id": 1,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "abc",
                    "body": "a",
                    "path": "f.py",
                    "line": 1,
                }
            ],
            [
                {
                    "id": 2,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "abc",
                    "body": "b",
                    "path": "f.py",
                    "line": 2,
                },
                {
                    "id": 3,
                    "user": {"login": "cursor[bot]"},
                    "commit_id": "abc",
                    "body": "c",
                    "path": "f.py",
                    "line": 3,
                },
            ],
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed(pages_payload)
        all_inline_comments = (
            fetch_bugbot_inline_comments_module.fetch_bugbot_inline_comments(
                owner="acme", repo="widget", number=42, current_head="abc"
            )
        )
    assert [each_comment["comment_id"] for each_comment in all_inline_comments] == [
        1,
        2,
        3,
    ]


def test_should_raise_when_gh_subprocess_fails() -> None:
    failure = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="auth failure"
    )
    with patch("subprocess.run", side_effect=failure):
        with pytest.raises(subprocess.CalledProcessError):
            fetch_bugbot_inline_comments_module.fetch_bugbot_inline_comments(
                owner="acme", repo="widget", number=42, current_head="abc"
            )
