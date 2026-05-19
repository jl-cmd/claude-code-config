"""Tests for check_convergence.

Covers the bugteam audit gate (`_check_bugteam_clean`) which identifies
bugteam reviews by body header signature rather than by the posting user's
GitHub login. Three scenarios are exercised:

- a clean bugteam review on the current HEAD passes the gate
- a dirty bugteam review on the current HEAD fails the gate
- the absence of any bugteam review on the current HEAD fails the gate
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).absolute().parent
_PR_CONVERGE_DIRECTORY = _SCRIPTS_DIRECTORY.parent

if str(_PR_CONVERGE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_PR_CONVERGE_DIRECTORY))


def _load_module() -> ModuleType:
    for each_cached_name in [
        each_key
        for each_key in list(sys.modules)
        if each_key == "config" or each_key.startswith("config.")
    ]:
        sys.modules.pop(each_cached_name, None)
    if str(_PR_CONVERGE_DIRECTORY) in sys.path:
        sys.path.remove(str(_PR_CONVERGE_DIRECTORY))
    sys.path.insert(0, str(_PR_CONVERGE_DIRECTORY))
    module_path = _SCRIPTS_DIRECTORY / "check_convergence.py"
    spec = importlib.util.spec_from_file_location(
        "check_convergence_under_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_convergence = _load_module()

CURRENT_HEAD_SHA = "abcdef1234567890abcdef1234567890abcdef12"
OTHER_HEAD_SHA = "0000000000000000000000000000000000000000"
CLEAN_BUGTEAM_BODY = (
    "**Bugteam audit completed** —— Clean — no findings\n"
    "\n"
    "---\n"
    "### Audit pass clean\n"
    "\n"
    "The Bugteam audit pass against commit `abcdef1` found no findings.\n"
)
DIRTY_BUGTEAM_BODY = (
    "**Bugteam audit completed** —— Findings requested\n"
    "\n"
    "---\n"
    "### Findings recorded as inline review comments\n"
    "\n"
    "The Bugteam audit pass against commit `abcdef1` surfaced 2 finding(s).\n"
)
NON_BUGTEAM_BODY = (
    "Cursor Bugbot has reviewed your changes and found 0 potential issues."
)


def _make_stub_gh_paginated(
    all_review_objects: list[dict[str, object]],
) -> Callable[[str], tuple[int, str]]:
    pages_payload = [all_review_objects]
    serialized = json.dumps(pages_payload)

    def stub_gh_api_paginated(endpoint_path: str) -> tuple[int, str]:
        return 0, serialized

    return stub_gh_api_paginated


def should_pass_when_clean_bugteam_review_present_on_current_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews_payload = [
        {
            "id": 1001,
            "body": CLEAN_BUGTEAM_BODY,
            "commit_id": CURRENT_HEAD_SHA,
            "submitted_at": "2026-05-17T12:00:00Z",
        }
    ]
    stub = _make_stub_gh_paginated(reviews_payload)
    monkeypatch.setattr(check_convergence, "_gh_api_paginated", stub)
    passed, detail = check_convergence._check_bugteam_clean(
        owner="JonEcho",
        repo="tests",
        number=42,
        head_sha=CURRENT_HEAD_SHA,
    )
    assert passed is True
    assert "clean bugteam audit" in detail
    assert CURRENT_HEAD_SHA[:7] in detail


def should_fail_when_dirty_bugteam_review_present_on_current_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews_payload = [
        {
            "id": 1002,
            "body": DIRTY_BUGTEAM_BODY,
            "commit_id": CURRENT_HEAD_SHA,
            "submitted_at": "2026-05-17T12:00:00Z",
        }
    ]
    stub = _make_stub_gh_paginated(reviews_payload)
    monkeypatch.setattr(check_convergence, "_gh_api_paginated", stub)
    passed, detail = check_convergence._check_bugteam_clean(
        owner="JonEcho",
        repo="tests",
        number=42,
        head_sha=CURRENT_HEAD_SHA,
    )
    assert passed is False
    assert "dirty bugteam audit" in detail
    assert CURRENT_HEAD_SHA[:7] in detail


def should_fail_when_no_bugteam_review_present_on_current_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews_payload = [
        {
            "id": 1003,
            "body": NON_BUGTEAM_BODY,
            "commit_id": CURRENT_HEAD_SHA,
            "submitted_at": "2026-05-17T12:00:00Z",
        },
        {
            "id": 1004,
            "body": CLEAN_BUGTEAM_BODY,
            "commit_id": OTHER_HEAD_SHA,
            "submitted_at": "2026-05-17T11:00:00Z",
        },
    ]
    stub = _make_stub_gh_paginated(reviews_payload)
    monkeypatch.setattr(check_convergence, "_gh_api_paginated", stub)
    passed, detail = check_convergence._check_bugteam_clean(
        owner="JonEcho",
        repo="tests",
        number=42,
        head_sha=CURRENT_HEAD_SHA,
    )
    assert passed is False
    assert "no bugteam review found" in detail


def should_fail_with_shape_detail_when_gh_returns_non_list_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error_object_payload = {"message": "Not Found", "documentation_url": "https://docs.github.com/rest"}
    serialized_error = json.dumps(error_object_payload)

    def stub_gh_api_paginated_returning_object(endpoint_path: str) -> tuple[int, str]:
        return 0, serialized_error

    monkeypatch.setattr(
        check_convergence, "_gh_api_paginated", stub_gh_api_paginated_returning_object
    )
    passed, detail = check_convergence._check_bugteam_clean(
        owner="JonEcho",
        repo="tests",
        number=42,
        head_sha=CURRENT_HEAD_SHA,
    )
    assert passed is False
    assert "unexpected gh api response shape" in detail


def test_private_helpers_recognize_clean_new_header_body() -> None:
    assert check_convergence._is_bugteam_review(CLEAN_BUGTEAM_BODY) is True
    assert check_convergence._is_clean_bugteam_review(CLEAN_BUGTEAM_BODY) is True


def test_private_helpers_recognize_dirty_new_header_body() -> None:
    assert check_convergence._is_bugteam_review(DIRTY_BUGTEAM_BODY) is True
    assert check_convergence._is_clean_bugteam_review(DIRTY_BUGTEAM_BODY) is False


def test_private_helpers_reject_non_bugteam_body() -> None:
    assert check_convergence._is_bugteam_review(NON_BUGTEAM_BODY) is False
    assert check_convergence._is_clean_bugteam_review(NON_BUGTEAM_BODY) is False
