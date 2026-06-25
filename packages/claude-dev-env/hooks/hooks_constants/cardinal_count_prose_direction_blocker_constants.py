"""Constants for the cardinal-count directional-prose blocker.

The rule file docstring-prose-matches-implementation.md describes the gate
check_docstring_cardinal_count_matches_constant_family. That gate fires whenever
a docstring's stated cardinal count is not equal to the size of a referenced
constant family: a count above the family size and a count below it both trip
the gate, because the binding condition is the set-membership test
len(family_members) not in stated_cardinals. When the rule prose describes that
symmetric condition with a directional comparator -- 'a count below the family
size' or 'references more members ... than the count names' -- and names no
symmetry marker beside it, the prose narrows the gate to one direction and
drifts from what the detector flags, the same companion-doc drift the rule
itself governs. This module holds the target rule basename, the cardinal-gate
anchor token, the directional-phrase patterns, the symmetry-marker pattern and
its window radius, the issue budget, and the block-message text the hook emits.
"""

import re

__all__ = [
    "TARGET_RULE_BASENAME",
    "CARDINAL_GATE_ANCHOR",
    "ALL_DIRECTIONAL_PROSE_PATTERNS",
    "SYMMETRY_MARKER_PATTERN",
    "SYMMETRY_WINDOW_RADIUS",
    "MAX_DIRECTION_ISSUES",
    "DIRECTION_MESSAGE_TEMPLATE",
    "DIRECTION_SYSTEM_MESSAGE",
    "DIRECTION_ADDITIONAL_CONTEXT",
]

TARGET_RULE_BASENAME: str = "docstring-prose-matches-implementation.md"

CARDINAL_GATE_ANCHOR: str = "check_docstring_cardinal_count_matches_constant_family"

ALL_DIRECTIONAL_PROSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:below|above|under|over|more\s+than|fewer\s+than|less\s+than|"
        r"greater\s+than|exceed(?:s|ing)?)\b[^.\n]{0,30}?\bfamily\s+size\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:more|fewer|less|greater)\s+members\b[^.\n]{0,80}?"
        r"\bthan\s+the\s+count\s+names\b",
        re.IGNORECASE,
    ),
)

SYMMETRY_MARKER_PATTERN: re.Pattern[str] = re.compile(
    r"differ|mismatch|not\s+equal|\bboth\b|\beither\b|"
    r"(?:above|over)\s+(?:and|or)\s+(?:below|under)|"
    r"(?:below|under)\s+(?:and|or)\s+(?:above|over)",
    re.IGNORECASE,
)

SYMMETRY_WINDOW_RADIUS: int = 90

MAX_DIRECTION_ISSUES: int = 4

DIRECTION_MESSAGE_TEMPLATE: str = (
    "{rule_basename} describes the cardinal-count gate "
    "(check_docstring_cardinal_count_matches_constant_family) with directional "
    "phrasing '{matched_phrase}', but the gate fires on any count mismatch: its "
    "binding condition is the set-membership test len(family_members) not in "
    "stated_cardinals, which a stated count above the family size and one below "
    "it both satisfy. State the condition symmetrically -- for example 'a count "
    "that differs from the family size' or 'the family member count differs from "
    "every stated cardinal' -- so the rule prose matches what the gate detects, "
    "rather than naming only the under-count or over-count direction."
)

DIRECTION_SYSTEM_MESSAGE: str = (
    "Directional phrasing in docstring-prose-matches-implementation.md narrows "
    "the cardinal-count gate's symmetric mismatch condition - restate it as 'a "
    "count that differs from the family size' in this same change"
)

DIRECTION_ADDITIONAL_CONTEXT: str = (
    "The gate check_docstring_cardinal_count_matches_constant_family fires when a "
    "docstring's stated cardinal count is not equal to the size of a referenced "
    "constant family (len(family_members) not in stated_cardinals). Both an "
    "over-count and an under-count trip it. Describe the gate trigger "
    "symmetrically ('a count that differs from the family size'); do not narrow it "
    "to one direction with 'below the family size' or 'more members ... than the "
    "count names'."
)
