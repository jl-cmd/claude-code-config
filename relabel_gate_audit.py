"""Post-hoc relabel pass for the gate-audit report.

Reads ``gate_audit_report.json`` (produced by the live-enforcer audit), rebuckets
findings currently labeled ``code_rules_other`` against the
``KEYWORD_TO_RULE_LABEL`` mapping in ``config.gate_audit_relabel_constants``,
recomputes the per-rule aggregates, and writes the updated report to
``gate_audit_report_relabeled.json``.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from pathlib import Path

from config.gate_audit_relabel_constants import (
    ALL_KEYWORD_TO_RULE_LABEL,
    DEFAULT_TOP_RULES_TO_REPORT,
    EVIDENCE_EXCERPT_KEY,
    FINDINGS_KEY,
    GATE_LEAKS_BY_RULE_KEY,
    INPUT_NOT_FOUND_MESSAGE,
    INPUT_REPORT_FILENAME,
    JSON_INDENT_WIDTH,
    LINE_NUMBER_PREFIX,
    LINE_NUMBER_SUFFIX,
    LOGGER_FORMATTER_PATTERN,
    LOGGER_NAME,
    OUTPUT_REPORT_FILENAME,
    OUTPUT_WRITTEN_MESSAGE,
    RESIDUAL_RULE_LABEL,
    RULE_COUNT_KEY,
    RULE_KEY,
    SUMMARY_KEY,
    TEXT_FILE_ENCODING,
    TOP_LEAKING_RULES_KEY,
)


_logger = logging.getLogger(LOGGER_NAME)
if not _logger.handlers:
    _stderr_handler = logging.StreamHandler(sys.stderr)
    _stderr_handler.setFormatter(logging.Formatter(LOGGER_FORMATTER_PATTERN))
    _logger.addHandler(_stderr_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def strip_line_number_prefix(evidence_excerpt: str) -> str:
    """Strip the ``Line N: `` prefix from an enforcer excerpt; return remainder."""
    if not evidence_excerpt.startswith(LINE_NUMBER_PREFIX):
        return evidence_excerpt
    suffix_index = evidence_excerpt.find(LINE_NUMBER_SUFFIX, len(LINE_NUMBER_PREFIX))
    if suffix_index == -1:
        return evidence_excerpt
    return evidence_excerpt[suffix_index + len(LINE_NUMBER_SUFFIX) :]


def relabel_excerpt(evidence_excerpt: str) -> str:
    """Map an excerpt to a precise rule label, or the residual catch-all."""
    message_text = strip_line_number_prefix(evidence_excerpt)
    for each_keyword, each_rule_label in ALL_KEYWORD_TO_RULE_LABEL:
        if each_keyword in message_text:
            return each_rule_label
    return RESIDUAL_RULE_LABEL


def relabel_findings_in_place(all_findings: list[dict]) -> None:
    """Rebucket every finding currently tagged with the residual rule label."""
    for each_finding in all_findings:
        if each_finding.get(RULE_KEY) != RESIDUAL_RULE_LABEL:
            continue
        excerpt_text = each_finding.get(EVIDENCE_EXCERPT_KEY, "")
        each_finding[RULE_KEY] = relabel_excerpt(excerpt_text)


def recompute_rule_counts(all_findings: list[dict]) -> dict[str, int]:
    """Aggregate findings by their (possibly updated) rule label."""
    return dict(
        Counter(each_finding.get(RULE_KEY, "") for each_finding in all_findings)
    )


def compute_top_leaking_rules(
    count_by_rule: dict[str, int],
    top_n: int = DEFAULT_TOP_RULES_TO_REPORT,
) -> list[dict]:
    """Return the top-N rules sorted by count descending, then rule name."""
    sorted_rules = sorted(
        count_by_rule.items(),
        key=lambda each_pair: (-each_pair[1], each_pair[0]),
    )
    return [
        {RULE_KEY: each_rule_name, RULE_COUNT_KEY: each_count}
        for each_rule_name, each_count in sorted_rules[:top_n]
    ]


def main() -> int:
    worktree_root = Path.cwd()
    input_path = worktree_root / INPUT_REPORT_FILENAME
    output_path = worktree_root / OUTPUT_REPORT_FILENAME

    if not input_path.exists():
        _logger.error(INPUT_NOT_FOUND_MESSAGE.format(path=input_path))
        return 1

    report_payload = json.loads(input_path.read_text(encoding=TEXT_FILE_ENCODING))
    all_findings = report_payload[FINDINGS_KEY]

    relabel_findings_in_place(all_findings)
    count_by_rule = recompute_rule_counts(all_findings)

    report_payload[GATE_LEAKS_BY_RULE_KEY] = count_by_rule
    summary_section = report_payload.setdefault(SUMMARY_KEY, {})
    summary_section[TOP_LEAKING_RULES_KEY] = compute_top_leaking_rules(count_by_rule)

    output_path.write_text(
        json.dumps(report_payload, indent=JSON_INDENT_WIDTH),
        encoding=TEXT_FILE_ENCODING,
    )
    _logger.info(OUTPUT_WRITTEN_MESSAGE.format(path=output_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
