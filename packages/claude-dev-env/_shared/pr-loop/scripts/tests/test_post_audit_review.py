import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest


def _load_module(module_name: str, filename: str) -> ModuleType:
    module_path = Path(__file__).parent.parent / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(module_name, module)
    spec.loader.exec_module(module)
    return module


post_audit_review = _load_module("post_audit_review", "post_audit_review.py")


class DescribeParseIdentifierAndUrl:
    def test_extracts_id_and_html_url_from_valid_response(self):
        raw = json.dumps({"id": 42, "html_url": "https://github.com/pr#review-42"})
        result = post_audit_review._parse_identifier_and_url(raw, "review")
        assert result == ("42", "https://github.com/pr#review-42")

    def test_returns_none_on_invalid_json(self):
        assert post_audit_review._parse_identifier_and_url("not json", "review") is None

    def test_returns_none_when_id_missing(self):
        raw = json.dumps({"html_url": "https://github.com/pr"})
        assert post_audit_review._parse_identifier_and_url(raw, "review") is None

    def test_returns_none_when_url_not_string(self):
        raw = json.dumps({"id": 1, "html_url": 99})
        assert post_audit_review._parse_identifier_and_url(raw, "review") is None


class DescribeValidateFindingCounts:
    def test_returns_none_when_counts_match(self):
        error = post_audit_review._validate_finding_counts(
            [Path("f1.md")], ["src/a.py"], [10]
        )
        assert error is None

    def test_returns_error_when_finding_count_mismatches_paths(self):
        error = post_audit_review._validate_finding_counts(
            [Path("f1.md"), Path("f2.md")], ["src/a.py"], [10, 20]
        )
        assert "2 finding-files, 1 paths" in error

    def test_returns_error_when_finding_count_mismatches_lines(self):
        error = post_audit_review._validate_finding_counts(
            [Path("f1.md")], ["src/a.py", "src/b.py"], [10]
        )
        assert "1 finding-files, 2 paths" in error


class DescribeBuildOutputPayload:
    def test_builds_correct_json_structure(self):
        output = post_audit_review._build_output_payload(
            "99",
            "https://github.com/pr#review-99",
            [("101", "https://github.com/pr#comment-101")],
        )
        payload = json.loads(output)
        assert payload["review_id"] == "99"
        assert payload["review_url"] == "https://github.com/pr#review-99"
        assert len(payload["comments"]) == 1
        assert payload["comments"][0]["id"] == "101"

    def test_handles_multiple_comments(self):
        output = post_audit_review._build_output_payload(
            "1", "url1", [("2", "url2"), ("3", "url3")]
        )
        payload = json.loads(output)
        assert len(payload["comments"]) == 2


class DescribePostReviewSummary:
    def test_returns_id_and_url_on_success(self):
        response = json.dumps({"id": 99, "html_url": "https://github.com/pr#review-99"})
        with patch.object(
            post_audit_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {"returncode": 0, "stdout": response, "stderr": "", "is_timed_out": False},
            )(),
        ):
            result = post_audit_review.post_review_summary(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_file=Path("body.md"),
            )
        assert result == ("99", "https://github.com/pr#review-99")

    def test_returns_none_on_gh_failure(self):
        with patch.object(
            post_audit_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {"returncode": 1, "stdout": "", "stderr": "gh error", "is_timed_out": False},
            )(),
        ):
            result = post_audit_review.post_review_summary(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_file=Path("body.md"),
            )
        assert result is None


class DescribePostComment:
    def test_returns_id_and_url_on_success(self):
        response = json.dumps({"id": 55, "html_url": "https://github.com/pr#comment-55"})
        with patch.object(
            post_audit_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {"returncode": 0, "stdout": response, "stderr": "", "is_timed_out": False},
            )(),
        ):
            result = post_audit_review.post_comment(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_file=Path("finding.md"),
                path="src/file.py",
                line=42,
            )
        assert result == ("55", "https://github.com/pr#comment-55")

    def test_returns_none_on_gh_failure(self):
        with patch.object(
            post_audit_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {"returncode": 1, "stdout": "", "stderr": "gh error", "is_timed_out": False},
            )(),
        ):
            result = post_audit_review.post_comment(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_file=Path("finding.md"),
                path="src/file.py",
                line=42,
            )
        assert result is None