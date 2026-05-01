"""Constants for the gate-audit relabel pass.

Module-scope mapping that converts an enforcer issue excerpt's leading phrase
into a precise rule label. Used by ``relabel_gate_audit.py`` to rebucket
findings currently labeled ``code_rules_other``.
"""

from __future__ import annotations


ALL_KEYWORD_TO_RULE_LABEL: tuple[tuple[str, str], ...] = (
    ("Constant ", "constants_location"),
    ("Unjustified # type: ignore", "unjustified_type_ignore"),
    ("Banned identifier ", "banned_identifier"),
    ("missing type annotation", "complete_type_hints"),
    ("missing return type annotation", "complete_type_hints"),
    ("inline list literal", "magic_values"),
    ("inline set literal", "magic_values"),
    ("inline tuple literal", "magic_values"),
    ("inline dict literal", "magic_values"),
    ("Magic value ", "magic_values"),
    ("Structural literal", "magic_values"),
    ("string magic value", "magic_values"),
    ("tests must cover behavior", "tdd_no_paired_test"),
    ("constant-value test", "useless_test"),
)
RESIDUAL_RULE_LABEL: str = "code_rules_other"
LINE_NUMBER_PREFIX: str = "Line "
LINE_NUMBER_SUFFIX: str = ": "

FINDINGS_KEY: str = "findings"
RULE_KEY: str = "rule"
EVIDENCE_EXCERPT_KEY: str = "evidence_excerpt"
GATE_LEAKS_BY_RULE_KEY: str = "gate_leaks_by_rule"
SUMMARY_KEY: str = "summary"
TOP_LEAKING_RULES_KEY: str = "top_leaking_rules"
RULE_COUNT_KEY: str = "count"

DEFAULT_TOP_RULES_TO_REPORT: int = 5
INPUT_REPORT_FILENAME: str = "gate_audit_report.json"
OUTPUT_REPORT_FILENAME: str = "gate_audit_report_relabeled.json"
JSON_INDENT_WIDTH: int = 2
TEXT_FILE_ENCODING: str = "utf-8"

LOGGER_NAME: str = "relabel_gate_audit"
LOGGER_FORMATTER_PATTERN: str = "%(name)s: %(message)s"
INPUT_NOT_FOUND_MESSAGE: str = "input report not found: {path}"
OUTPUT_WRITTEN_MESSAGE: str = "wrote relabeled report to {path}"
