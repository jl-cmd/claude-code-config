import importlib.util
import inspect
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

    def test_returns_none_when_response_is_a_json_array(self):
        raw = json.dumps([{"id": 42, "html_url": "https://github.com/pr"}])
        assert post_audit_review._parse_review_response(raw) is None

    def test_returns_none_when_response_is_a_json_scalar(self):
        raw = json.dumps(42)
        assert post_audit_review._parse_review_response(raw) is None

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

    def test_returns_success_when_post_response_omits_comments_field(self):
        """The GitHub REST API POST /reviews response does NOT include inline
        comments — they are returned via a separate GET /reviews/{id}/comments
        call. Success must therefore be signaled by the review object alone,
        regardless of how many comments were sent in the request payload.
        """
        raw = json.dumps({"id": 42, "html_url": "https://github.com/pr#review-42"})
        result = post_audit_review._parse_review_response(raw)
        assert result is not None
        review_id, review_url, all_comment_entries = result
        assert review_id == "42"
        assert review_url == "https://github.com/pr#review-42"
        assert all_comment_entries == []


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


class DescribePostReviewUsesShouldRetryParameterNames:
    """The call to run_gh inside post_review must pass the renamed boolean
    parameters `should_retry_nonzero` and `should_retry_timeout` (CODE_RULES
    §5 boolean prefix).
    """

    def test_post_review_passes_should_retry_kwargs_to_run_gh(self):
        captured_call_kwargs: dict[str, object] = {}

        def fake_run_gh(*_args: object, **kwargs: object) -> object:
            captured_call_kwargs.update(kwargs)
            return type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps({"id": 1, "html_url": "u", "comments": []}),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )()

        with patch.object(post_audit_review, "run_gh", side_effect=fake_run_gh):
            post_audit_review.post_review(
                owner="own",
                repo="rep",
                pull_number=1,
                commit_id="abc",
                body_text="body",
                all_comments=[],
            )
        assert captured_call_kwargs.get("should_retry_nonzero") is False
        assert captured_call_kwargs.get("should_retry_timeout") is False
        assert "retry_nonzero" not in captured_call_kwargs
        assert "retry_timeout" not in captured_call_kwargs


class DescribeParseReviewResponseUsesDomainIdentifiers:
    """Local identifiers in `_parse_review_response` must follow CODE_RULES §5:
    no banned `response` substring (use `parsed_review_object`) and `all_`
    prefix on collection variables (use `all_nested_comments`).
    """

    def test_parse_review_response_uses_domain_identifiers(self):
        parse_review_response_source_text = inspect.getsource(
            post_audit_review._parse_review_response
        )
        assert "parsed_review_object = json.loads(" in parse_review_response_source_text
        assert (
            "all_nested_comments = parsed_review_object.get("
            in parse_review_response_source_text
        )
        assert "response_payload" not in parse_review_response_source_text
        assert " nested_comments = " not in parse_review_response_source_text


class DescribeBuildOutputPayloadUsesDomainIdentifier:
    """The local payload variable in `_build_output_payload` must avoid the
    banned word `output` and use the domain-meaningful name
    `review_summary_payload` (CODE_RULES §5 banned-name list).
    """

    def test_build_output_payload_uses_review_summary_payload(self):
        build_output_payload_source_text = inspect.getsource(
            post_audit_review._build_output_payload
        )
        assert (
            "review_summary_payload: dict[str, object] = {"
            in build_output_payload_source_text
        )
        assert "return json.dumps(review_summary_payload)" in build_output_payload_source_text
        assert "output_payload: dict" not in build_output_payload_source_text
        assert "json.dumps(output_payload)" not in build_output_payload_source_text


class DescribeMainUsesDomainIdentifier:
    """The destructured posted-review tuple in `main` must avoid the banned
    word `result` (CODE_RULES §5 banned-name list) and use `posted_review`.
    """

    def test_main_uses_posted_review_identifier(self):
        main_source_text = inspect.getsource(post_audit_review.main)
        assert "posted_review = post_review(" in main_source_text
        assert "if posted_review is None:" in main_source_text
        assert (
            "review_identifier, review_url, all_comment_entries = posted_review"
            in main_source_text
        )
        assert "review_result" not in main_source_text