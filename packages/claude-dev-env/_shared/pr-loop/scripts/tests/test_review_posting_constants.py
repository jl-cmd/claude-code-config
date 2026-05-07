"""Tests for review_posting_constants.py extracted constant set."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = (
        Path(__file__).parent.parent / "config" / "review_posting_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "config.review_posting_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_reviews_path_template_renders_with_pull_number_placeholder() -> None:
    rendered_path = constants_module.REVIEWS_PATH_TEMPLATE.format(
        owner="o", repo="r", pull_number=42
    )
    assert rendered_path == "/repos/o/r/pulls/42/reviews?per_page=100"


def test_review_post_timeout_seconds_is_positive_integer() -> None:
    assert isinstance(constants_module.REVIEW_POST_TIMEOUT_SECONDS, int)
    assert constants_module.REVIEW_POST_TIMEOUT_SECONDS > 0


def test_review_comments_endpoint_template_renders_with_review_id() -> None:
    rendered_path = constants_module.REVIEW_COMMENTS_ENDPOINT_TEMPLATE.format(
        owner="o", repo="r", pull_number=42, review_id=99
    )
    assert rendered_path == "/repos/o/r/pulls/42/reviews/99/comments?per_page=100"


def test_status_ok_constant_pins_orchestrator_contract_string() -> None:
    """Producer/consumer contract: verify_review.py emits this exact string;
    the orchestrator reads it. Pinning here prevents silent drift between
    the two sides of the boundary.
    """
    assert constants_module.STATUS_OK == "ok"
    assert isinstance(constants_module.STATUS_OK, str)
