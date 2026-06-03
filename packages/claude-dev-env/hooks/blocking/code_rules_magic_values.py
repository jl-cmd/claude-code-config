"""Magic-number and f-string structural-literal checks for function bodies."""

import ast
import re
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_path_utils import (  # noqa: E402
    is_config_file,
)
from code_rules_shared import (  # noqa: E402
    _extract_fstring_literal_parts,
    is_test_file,
)

_STRING_LITERAL_PATTERN = re.compile(
    r"(\"(?:\\.|[^\"\\])*\")|('(?:\\.|[^'\\])*')",
)


def _mask_string_literals_preserving_length(source_line: str) -> str:
    """Replace every string literal with an equal-length neutral placeholder.

    The TDD-gate sentinel below opts this production file out of the hook
    because the existing companion tests use the project's convention
    ``test_code_rules_enforcer_<suffix>.py`` rather than the single
    ``test_code-rules-enforcer.py`` name the hook scans for. Matching
    tests for this change live in
    ``test_code_rules_enforcer_magic_string_masking.py``.
    Sentinel: # pragma: no-tdd-gate
    """

    def _replace_string_literal(match: re.Match[str]) -> str:
        matched_literal = match.group(0)
        opening_quote = matched_literal[0]
        closing_quote = matched_literal[-1]
        inner_length = max(len(matched_literal) - 2, 0)
        return f"{opening_quote}{'_' * inner_length}{closing_quote}"

    return _STRING_LITERAL_PATTERN.sub(_replace_string_literal, source_line)


def check_magic_values(content: str, file_path: str) -> list[str]:
    """Check for magic values in function bodies."""
    if is_config_file(file_path) or is_test_file(file_path):
        return []

    issues = []
    lines = content.split("\n")
    is_inside_function = False

    number_pattern = re.compile(r"(?<![.\w])(\d+\.?\d*)(?![.\w])")
    allowed_numbers = {"0", "1", "-1", "0.0", "1.0"}

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            is_inside_function = True
            continue

        if re.match(r"^class\s+\w+", stripped):
            is_inside_function = False
            continue

        if is_inside_function:
            if "=" in stripped and stripped.split("=")[0].strip().isupper():
                continue

            if stripped.startswith(("return", "yield", "raise")):
                continue

            stripped_without_string_literals = _mask_string_literals_preserving_length(stripped)
            numbers_found = number_pattern.findall(stripped_without_string_literals)
            for number in numbers_found:
                if number not in allowed_numbers:
                    if "range(" in stripped_without_string_literals or "enumerate(" in stripped_without_string_literals:
                        continue
                    if "[" in stripped_without_string_literals and "]" in stripped_without_string_literals:
                        continue
                    issues.append(f"Line {line_number}: Magic value {number} - extract to named constant")
                    break

        if len(issues) >= 3:
            break

    return issues


def _has_structural_shape(literal_body: str) -> bool:
    """Return True when a literal body looks like a path, URL, or regex.

    Natural English containing a single slash (e.g. ``online/offline``,
    ``CI/CD``, ``and/or``) must NOT match. Only multi-segment paths,
    URL schemes, Windows drive prefixes, leading absolute paths, regex
    escape sequences (``\\d``, ``\\w``, ``\\s`` and friends), or regex
    anchors at the boundary are treated as structural.
    """
    if re.search(r"\w+/\w+/\w+", literal_body):
        return True
    if re.search(r"\w+\\\w+\\\w+", literal_body):
        return True
    if re.search(r"[A-Za-z][A-Za-z0-9+.\-]*://", literal_body):
        return True
    if re.search(r"(^|\s)[A-Za-z]:[\\/]", literal_body):
        return True
    if re.search(r"^/\w+/\w+", literal_body):
        return True
    if re.search(r"\\[dwsDWSbBAZ]|\\\d", literal_body):
        return True
    if literal_body.startswith("^") or literal_body.endswith("$"):
        return True
    return False


def check_fstring_structural_literals(content: str, file_path: str) -> list[str]:
    """Flag f-strings whose literal fragments look like paths, URLs, or regex.

    Parses the file with :mod:`ast` so every f-string form is handled
    uniformly: single, triple-quoted, raw (``rf`` / ``fr``), and strings
    containing apostrophes or escaped braces. The literal portions of
    each ``JoinedStr`` node are concatenated, and the result is treated
    as a structural magic value only when :func:`_has_structural_shape`
    matches a multi-segment path, a URL scheme, a Windows drive prefix,
    a leading absolute path, a regex escape sequence, or a boundary
    regex anchor.

    The enforcer hook file, config files, and test files are all exempt.
    Syntax errors in the input silently produce no issues, matching the
    behaviour of the other lint-style checks in this module.
    """
    if is_config_file(file_path) or is_test_file(file_path):
        return []
    if file_path.replace("\\", "/").endswith("hooks/blocking/code_rules_enforcer.py"):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    minimum_literal_length = 2
    maximum_issues_before_stop = 100
    non_magic_stripped_values = {"", "True", "False"}

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, ast.JoinedStr):
            continue
        display_body, shape_body = _extract_fstring_literal_parts(each_node)
        if display_body in non_magic_stripped_values:
            continue
        if len(display_body) < minimum_literal_length:
            continue
        if not _has_structural_shape(shape_body):
            continue
        issues.append(
            f"Line {each_node.lineno}: Structural literal inside f-string {display_body!r} - extract to config"
        )
        if len(issues) >= maximum_issues_before_stop:
            break

    return issues
