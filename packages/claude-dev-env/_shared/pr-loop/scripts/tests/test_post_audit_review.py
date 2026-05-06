import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


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


class DescribeParseReviewResponse:
    def test_extracts_review_id_url_and_empty_comments_when_no_nested_comments(self):
        raw = json.dumps({"id": 42, "html_url": "https://github.com/pr#review-42"})
        result = post_audit_review._parse_review_response(raw)
        assert result is not None
        review_id, review_url, all_comment_entries = result
        assert review_id == "42"
        assert review_url == "https://github.com/pr#review-42"
        assert all_comment_entries == []

    def test_extracts_nested_comment_infos(self):
        raw = json.dumps(
            {
                "id": 42,
                "html_url": "https://github.com/pr#review-42",
                "comments": [
                    {"id": 101, "html_url": "https://github.com/pr#comment-101"},
                    {"id": 102, "html_url": "https://github.com/pr#comment-102"},
                ],
            }
        )
        result = post_audit_review._parse_review_response(raw)
        assert result is not None
        review_id, review_url, all_comment_entries = result
        assert review_id == "42"
        assert review_url == "https://github.com/pr#review-42"
        assert all_comment_entries == [
            {"id": "101", "url": "https://github.com/pr#comment-101"},
            {"id": "102", "url": "https://github.com/pr#comment-102"},
        ]

    def test_returns_none_on_invalid_json(self):
        assert post_audit_review._parse_review_response("not json") is None

    def test_returns_none_when_id_missing(self):
        raw = json.dumps({"html_url": "https://github.com/pr"})
        assert post_audit_review._parse_review_response(raw) is None

    def test_returns_none_when_url_not_string(self):
        raw = json.dumps({"id": 1, "html_url": 99})
        assert post_audit_review._parse_review_response(raw) is None

    def test_skips_malformed_nested_comments(self):
        raw = json.dumps(
            {
                "id": 42,
                "html_url": "https://github.com/pr#review-42",
                "comments": [
                    {"id": 101, "html_url": "https://github.com/pr#comment-101"},
                    {"id": "not-a-number", "html_url": 99},
                ],
            }
        )
        result = post_audit_review._parse_review_response(raw)
        assert result is not None
        review_id, review_url, all_comment_entries = result
        assert all_comment_entries == [
            {"id": "101", "url": "https://github.com/pr#comment-101"},
        ]

    def test_returns_result_when_expected_count_matches(self):
        raw = json.dumps(
            {
                "id": 42,
                "html_url": "https://github.com/pr#review-42",
                "comments": [
                    {"id": 101, "html_url": "https://github.com/pr#comment-101"},
                    {"id": 102, "html_url": "https://github.com/pr#comment-102"},
                ],
            }
        )
        result = post_audit_review._parse_review_response(
            raw, expected_comment_count=2
        )
        assert result is not None
        review_id, review_url, all_comment_entries = result
        assert len(all_comment_entries) == 2

    def test_returns_none_when_expected_count_exceeds_returned(self):
        raw = json.dumps(
            {
                "id": 42,
                "html_url": "https://github.com/pr#review-42",
                "comments": [
                    {"id": 101, "html_url": "https://github.com/pr#comment-101"},
                ],
            }
        )
        assert (
            post_audit_review._parse_review_response(raw, expected_comment_count=3)
            is None
        )


class DescribeBuildOutputPayload:
    def test_builds_correct_json_structure(self):
        output = post_audit_review._build_output_payload(
            "99",
            "https://github.com/pr#review-99",
            [{"id": "101", "url": "https://github.com/pr#comment-101"}],
        )
        payload = json.loads(output)
        assert payload["review_id"] == "99"
        assert payload["review_url"] == "https://github.com/pr#review-99"
        assert len(payload["comments"]) == 1
        assert payload["comments"][0]["id"] == "101"

    def test_handles_multiple_comments(self):
        output = post_audit_review._build_output_payload(
            "1",
            "url1",
            [{"id": "2", "url": "url2"}, {"id": "3", "url": "url3"}],
        )
        payload = json.loads(output)
        assert len(payload["comments"]) == 2


class DescribePostReview:
    def test_returns_review_info_on_success(self):
        response = json.dumps(
            {
                "id": 99,
                "html_url": "https://github.com/pr#review-99",
                "comments": [
                    {"id": 101, "html_url": "https://github.com/pr#comment-101"}
                ],
            }
        )
        with patch.object(
            post_audit_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {"returncode": 0, "stdout": response, "stderr": "", "is_timed_out": False},
            )(),
        ):
            result = post_audit_review.post_review(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_text="review body",
                all_comments=[
                    {"path": "file.py", "line": 42, "side": "RIGHT", "body": "finding"}
                ],
            )
        assert result is not None
        review_id, review_url, all_comment_entries = result
        assert review_id == "99"
        assert review_url == "https://github.com/pr#review-99"
        assert all_comment_entries == [
            {"id": "101", "url": "https://github.com/pr#comment-101"}
        ]

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
            result = post_audit_review.post_review(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_text="review body",
                all_comments=[],
            )
        assert result is None