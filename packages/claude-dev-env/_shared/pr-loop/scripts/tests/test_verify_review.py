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


verify_review = _load_module("verify_review", "verify_review.py")


class DescribeBuildReviewsApiPath:
    def test_formats_owner_repo_number_into_api_path(self):
        path = verify_review._build_reviews_api_path("own", "rep", 42)
        assert "own" in path
        assert "rep" in path
        assert "42" in path
        assert path.startswith("/repos/")

    def test_returns_exact_paginated_reviews_path_for_owner_repo_number(self):
        api_path = verify_review._build_reviews_api_path("owner", "repo", 42)
        assert api_path == "/repos/owner/repo/pulls/42/reviews?per_page=100"


class DescribeBuildExpectedHeaders:
    def test_returns_both_header_variants_for_loop_3(self):
        loop_audit, bugteam_loop = verify_review._build_expected_headers(3)
        assert "3" in loop_audit
        assert "3" in bugteam_loop
        assert loop_audit.startswith("## Loop ")
        assert bugteam_loop.startswith("## /bugteam loop ")


class DescribeIsMatchingReview:
    def test_matches_loop_audit_header(self):
        headers = ("## Loop 3 Audit", "## /bugteam loop 3")
        assert verify_review._is_matching_review(
            "## Loop 3 Audit — Merged Findings", headers
        )

    def test_matches_bugteam_loop_header(self):
        headers = ("## Loop 1 Audit", "## /bugteam loop 1")
        assert verify_review._is_matching_review("## /bugteam loop 1", headers)

    def test_rejects_unrelated_body(self):
        headers = ("## Loop 2 Audit", "## /bugteam loop 2")
        assert not verify_review._is_matching_review("## Pull request overview", headers)

    def test_treats_none_body_as_empty(self):
        headers = ("## Loop 1 Audit", "## /bugteam loop 1")
        assert not verify_review._is_matching_review(None, headers)


class DescribeParsePaginatedSlurpResponse:
    def test_flattens_array_of_pages(self):
        raw = json.dumps([[{"a": 1}], [{"b": 2}, {"c": 3}]])
        result = verify_review._parse_paginated_slurp_response(raw)
        assert result == [{"a": 1}, {"b": 2}, {"c": 3}]

    def test_returns_none_for_invalid_json(self):
        assert verify_review._parse_paginated_slurp_response("not json") is None

    def test_returns_none_when_root_is_not_list(self):
        assert verify_review._parse_paginated_slurp_response('"string"') is None

    def test_returns_none_when_page_is_not_list(self):
        raw = json.dumps([[{"a": 1}], "not-a-page"])
        assert verify_review._parse_paginated_slurp_response(raw) is None

    def test_returns_none_when_item_is_not_dict(self):
        raw = json.dumps([[{"a": 1}, 42]])
        assert verify_review._parse_paginated_slurp_response(raw) is None


class DescribeVerifyPrReview:
    def test_returns_exit_ok_when_exactly_one_review_matches(self):
        sample_review = {
            "id": 99,
            "body": "## Loop 3 Audit — Merged Findings",
            "commit_id": "abc1234",
            "html_url": "https://github.com/own/rep/pull/1#review-99",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[sample_review]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review("own", "rep", 1, "abc1234", 3)
        assert exit_code == 0

    def test_returns_exit_no_review_when_no_matching_loop_header(self):
        wrong_review = {
            "id": 1,
            "body": "## Pull request overview",
            "commit_id": "abc1234",
            "html_url": "url",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[wrong_review]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review("own", "rep", 1, "abc1234", 3)
        assert exit_code == 1

    def test_returns_exit_wrong_commit_when_commit_id_differs(self):
        review = {
            "id": 1,
            "body": "## Loop 3 Audit",
            "commit_id": "wrong99",
            "html_url": "url",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[review]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review("own", "rep", 1, "abc1234", 3)
        assert exit_code == 2

    def test_wrong_commit_path_iterates_all_matching_reviews(self):
        first_stale = {
            "id": 1,
            "body": "## Loop 3 Audit",
            "commit_id": "stale_one",
            "html_url": "url-1",
        }
        second_stale = {
            "id": 2,
            "body": "## /bugteam loop 3 ",
            "commit_id": "stale_two",
            "html_url": "url-2",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[first_stale, second_stale]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review(
                "own", "rep", 1, "expected_sha", 3
            )
        assert exit_code == 2

    def test_returns_exit_duplicate_when_multiple_matching_reviews(self):
        review_a = {
            "id": 1,
            "body": "## Loop 3 Audit",
            "commit_id": "abc1234",
            "html_url": "url1",
        }
        review_b = {
            "id": 2,
            "body": "## Loop 3 Audit — Second",
            "commit_id": "abc1234",
            "html_url": "url2",
        }
        with patch.object(
            verify_review,
            "run_gh",
            return_value=type(
                "GhResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps([[review_a, review_b]]),
                    "stderr": "",
                    "is_timed_out": False,
                },
            )(),
        ):
            exit_code = verify_review.verify_pr_review("own", "rep", 1, "abc1234", 3)
        assert exit_code == 3