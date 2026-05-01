"""Tests for the gate-audit relabel pass."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT_PATH = str(Path(__file__).resolve().parent)
_HOOKS_ROOT_PATH = str(
    Path(__file__).resolve().parent / "packages" / "claude-dev-env" / "hooks"
)
if _HOOKS_ROOT_PATH in sys.path:
    sys.path.remove(_HOOKS_ROOT_PATH)
for _each_cached_module_name in list(sys.modules):
    if _each_cached_module_name == "config" or _each_cached_module_name.startswith("config."):
        sys.modules.pop(_each_cached_module_name, None)
if _REPO_ROOT_PATH not in sys.path:
    sys.path.insert(0, _REPO_ROOT_PATH)

from relabel_gate_audit import (  # noqa: E402
    compute_top_leaking_rules,
    recompute_rule_counts,
    relabel_excerpt,
    relabel_findings_in_place,
    strip_line_number_prefix,
)


def test_strip_line_number_prefix_removes_leading_line_marker() -> None:
    excerpt = "Line 219: parameter 'x' missing type annotation (CODE_RULES §6)"

    stripped = strip_line_number_prefix(excerpt)

    assert stripped == "parameter 'x' missing type annotation (CODE_RULES §6)"


def test_strip_line_number_prefix_returns_input_when_no_prefix() -> None:
    excerpt = "no leading line marker here"

    stripped = strip_line_number_prefix(excerpt)

    assert stripped == excerpt


def test_strip_line_number_prefix_handles_multi_digit_line_numbers() -> None:
    excerpt = "Line 1234: inline list literal of 5 constants"

    stripped = strip_line_number_prefix(excerpt)

    assert stripped == "inline list literal of 5 constants"


def test_relabel_excerpt_maps_constant_keyword_to_constants_location() -> None:
    excerpt = "Line 12: Constant DEFAULT_TIMEOUT - move to config/"

    rule_label = relabel_excerpt(excerpt)

    assert rule_label == "constants_location"


def test_relabel_excerpt_maps_unjustified_type_ignore() -> None:
    excerpt = "Line 8: Unjustified # type: ignore comment - add reason"

    rule_label = relabel_excerpt(excerpt)

    assert rule_label == "unjustified_type_ignore"


def test_relabel_excerpt_maps_banned_identifier() -> None:
    excerpt = "Line 4: Banned identifier 'response' - use descriptive name"

    rule_label = relabel_excerpt(excerpt)

    assert rule_label == "banned_identifier"


def test_relabel_excerpt_maps_missing_type_annotation_to_complete_type_hints() -> None:
    excerpt = "Line 219: parameter 'validate_content' on 'run_gate' missing type annotation (CODE_RULES §6)"

    rule_label = relabel_excerpt(excerpt)

    assert rule_label == "complete_type_hints"


def test_relabel_excerpt_maps_inline_set_literal_to_magic_values() -> None:
    excerpt = "Line 33: inline set literal of 4 constants in function body - extract to config/"

    rule_label = relabel_excerpt(excerpt)

    assert rule_label == "magic_values"


def test_relabel_excerpt_maps_constant_value_test_to_useless_test() -> None:
    excerpt = "Line 88: constant-value test - delete"

    rule_label = relabel_excerpt(excerpt)

    assert rule_label == "useless_test"


def test_relabel_excerpt_returns_residual_label_for_unknown_excerpt() -> None:
    excerpt = "Line 7: something we have not mapped yet"

    rule_label = relabel_excerpt(excerpt)

    assert rule_label == "code_rules_other"


def test_relabel_findings_in_place_rebuckets_only_residual_rule_findings() -> None:
    findings = [
        {
            "rule": "code_rules_other",
            "evidence_excerpt": "Line 1: Constant FOO - move to config/",
        },
        {"rule": "magic_values", "evidence_excerpt": "Line 2: Magic value 42"},
        {
            "rule": "code_rules_other",
            "evidence_excerpt": "Line 3: Banned identifier 'response'",
        },
    ]

    relabel_findings_in_place(findings)

    assert findings[0]["rule"] == "constants_location"
    assert findings[1]["rule"] == "magic_values"
    assert findings[2]["rule"] == "banned_identifier"


def test_relabel_findings_in_place_leaves_unmapped_residuals_unchanged() -> None:
    findings = [
        {
            "rule": "code_rules_other",
            "evidence_excerpt": "Line 9: weird thing not in mapping",
        },
    ]

    relabel_findings_in_place(findings)

    assert findings[0]["rule"] == "code_rules_other"


def test_recompute_rule_counts_aggregates_findings_by_rule() -> None:
    findings = [
        {"rule": "magic_values"},
        {"rule": "magic_values"},
        {"rule": "constants_location"},
    ]

    count_by_rule = recompute_rule_counts(findings)

    assert count_by_rule == {"magic_values": 2, "constants_location": 1}


def test_compute_top_leaking_rules_returns_top_n_sorted_descending() -> None:
    count_by_rule = {
        "magic_values": 62,
        "constants_location": 48,
        "naming_collections": 123,
        "complete_type_hints": 8,
    }

    top_three = compute_top_leaking_rules(count_by_rule, top_n=3)

    assert top_three == [
        {"rule": "naming_collections", "count": 123},
        {"rule": "magic_values", "count": 62},
        {"rule": "constants_location", "count": 48},
    ]


def test_relabel_pass_against_real_report_drops_residual_below_threshold(
    tmp_path: Path,
) -> None:
    source_report_path = Path("gate_audit_report.json")
    if not source_report_path.exists():
        return

    report_payload = json.loads(source_report_path.read_text(encoding="utf-8"))
    findings = report_payload["findings"]
    relabel_findings_in_place(findings)
    count_by_rule = recompute_rule_counts(findings)

    assert count_by_rule.get("code_rules_other", 0) <= 5
