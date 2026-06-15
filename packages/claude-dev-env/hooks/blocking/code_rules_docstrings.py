"""Google-style docstring presence and docstring Args-versus-signature checks."""

import ast
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_shared import (  # noqa: E402
    _statement_is_docstring,
    _walk_skipping_nested_functions,
    _walk_skipping_type_checking_blocks,
    is_hook_infrastructure,
    is_test_file,
)

from hooks_constants.blocking_check_limits import (  # noqa: E402
    ALL_DOCSTRING_CLAIM_NEGATION_TOKENS,
    ALL_DOCSTRING_EXEMPT_DECORATOR_NAMES,
    ALL_DOCSTRING_FALL_THROUGH_CLAIM_PHRASES,
    ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES,
    ALL_DOCSTRING_UNCONDITIONAL_BREAK_CLAIM_PHRASES,
    DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT,
    MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES,
    MAX_DOCSTRING_FORMAT_ISSUES,
    MAX_DOCSTRING_LOOP_CONTROL_FLOW_ISSUES,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_DOCSTRING_ARGS_SECTION_HEADERS,
    ALL_DOCSTRING_TERMINATING_SECTION_HEADERS,
    ALL_SELF_AND_CLS_PARAMETER_NAMES,
    DOCSTRING_ARG_ENTRY_PATTERN,
)


def _function_is_private_or_dunder(function_name: str) -> bool:
    if function_name.startswith("__") and function_name.endswith("__"):
        return True
    return function_name.startswith("_")


def _decorator_label(decorator_node: ast.expr) -> str:
    if isinstance(decorator_node, ast.Name):
        return decorator_node.id
    if isinstance(decorator_node, ast.Attribute):
        prefix = (
            decorator_node.value.id
            if isinstance(decorator_node.value, ast.Name)
            else ""
        )
        return f"{prefix}.{decorator_node.attr}" if prefix else decorator_node.attr
    if isinstance(decorator_node, ast.Call):
        return _decorator_label(decorator_node.func)
    return ""


def _function_has_exempt_decorator(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    for each_decorator in function_node.decorator_list:
        if _decorator_label(each_decorator) in ALL_DOCSTRING_EXEMPT_DECORATOR_NAMES:
            return True
    return False


def _function_body_line_count(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    if not function_node.body:
        return 0
    first_body_index = 0
    if _statement_is_docstring(function_node.body[0]):
        if len(function_node.body) == 1:
            return 0
        first_body_index = 1
    last_statement = function_node.body[-1]
    end_line = getattr(last_statement, "end_lineno", last_statement.lineno)
    first_line = function_node.body[first_body_index].lineno
    return max(0, end_line - first_line + 1)


def _function_documentable_parameter_count(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    documentable_count = 0
    for each_argument in function_node.args.args:
        if each_argument.arg in ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES:
            continue
        documentable_count += 1
    documentable_count += len(function_node.args.kwonlyargs)
    for each_argument in function_node.args.posonlyargs:
        if each_argument.arg in ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES:
            continue
        documentable_count += 1
    if function_node.args.vararg is not None:
        documentable_count += 1
    if function_node.args.kwarg is not None:
        documentable_count += 1
    return documentable_count


def _annotation_is_explicit_none_return(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Constant) and annotation_node.value is None:
        return True
    return isinstance(annotation_node, ast.Name) and annotation_node.id == "None"


def _annotation_is_noreturn(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Name) and annotation_node.id == "NoReturn":
        return True
    return isinstance(annotation_node, ast.Attribute) and annotation_node.attr == "NoReturn"


def _function_body_contains_raise(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    return any(
        isinstance(each_descendant, ast.Raise)
        for each_descendant in _walk_skipping_nested_functions(function_node)
    )


def _function_body_contains_yield(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    return any(
        isinstance(each_descendant, (ast.Yield, ast.YieldFrom))
        for each_descendant in _walk_skipping_nested_functions(function_node)
    )


def _loop_bodies(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[list[ast.stmt]]:
    loop_bodies: list[list[ast.stmt]] = []
    for each_descendant in _walk_skipping_nested_functions(function_node):
        if isinstance(each_descendant, (ast.For, ast.AsyncFor, ast.While)):
            loop_bodies.append(list(each_descendant.body))
    return loop_bodies


def _statement_list_has_unconditional_break(all_statements: list[ast.stmt]) -> bool:
    for each_statement in all_statements:
        if isinstance(each_statement, ast.Break):
            return True
        if isinstance(each_statement, (ast.For, ast.AsyncFor, ast.While)):
            continue
        if _statement_subtree_has_unconditional_break(each_statement):
            return True
    return False


def _statement_subtree_has_unconditional_break(statement: ast.stmt) -> bool:
    if isinstance(statement, ast.If):
        return False
    if isinstance(statement, ast.Try):
        return _statement_list_has_unconditional_break(statement.body)
    if isinstance(statement, ast.With):
        return _statement_list_has_unconditional_break(statement.body)
    if isinstance(statement, ast.Match):
        return any(
            _match_case_is_wildcard(each_case)
            and _statement_list_has_unconditional_break(each_case.body)
            for each_case in statement.cases
        )
    return False


def _match_case_is_wildcard(match_case: ast.match_case) -> bool:
    if match_case.guard is not None:
        return False
    pattern = match_case.pattern
    return (
        isinstance(pattern, ast.MatchAs)
        and pattern.name is None
        and pattern.pattern is None
    )


def _any_loop_has_unconditional_break(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    return any(
        _statement_list_has_unconditional_break(each_body)
        for each_body in _loop_bodies(function_node)
    )


def _statement_subtree_is_loop_skip_path(node: ast.AST) -> bool:
    return isinstance(node, (ast.Continue, ast.If, ast.Match))


def _loop_body_has_skip_path(all_loop_statements: list[ast.stmt]) -> bool:
    for each_statement in all_loop_statements:
        if _statement_subtree_is_loop_skip_path(each_statement):
            return True
        for each_descendant in _walk_skipping_nested_functions(each_statement):
            if isinstance(each_descendant, (ast.For, ast.AsyncFor, ast.While)):
                continue
            if _statement_subtree_is_loop_skip_path(each_descendant):
                return True
    return False


def _function_loops_have_skip_path(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    return any(
        _loop_body_has_skip_path(each_body)
        for each_body in _loop_bodies(function_node)
    )


def _sentences_containing_phrase(lowered_text: str, phrase: str) -> list[str]:
    return [
        each_sentence
        for each_sentence in _split_into_sentences(lowered_text)
        if phrase in each_sentence
    ]


def _split_into_sentences(lowered_text: str) -> list[str]:
    sentences = lowered_text.replace("\n", " ")
    for each_terminator in (".", ";", ":"):
        sentences = sentences.replace(each_terminator, "\x00")
    return [each_segment for each_segment in sentences.split("\x00") if each_segment.strip()]


def _phrase_is_negated_in_sentence(sentence: str, phrase: str) -> bool:
    text_before_phrase = sentence.split(phrase, 1)[0]
    words_before_phrase = _words_in(text_before_phrase)
    if any(each_word in ALL_DOCSTRING_CLAIM_NEGATION_TOKENS for each_word in words_before_phrase):
        return True
    return any(
        " " in each_token and each_token in text_before_phrase
        for each_token in ALL_DOCSTRING_CLAIM_NEGATION_TOKENS
    )


def _words_in(text: str) -> list[str]:
    return [each_word.strip(",") for each_word in text.split() if each_word.strip(",")]


def _docstring_affirms_phrase(docstring_text: str, all_claim_phrases: frozenset[str]) -> bool:
    lowered_text = docstring_text.lower()
    for each_phrase in all_claim_phrases:
        for each_sentence in _sentences_containing_phrase(lowered_text, each_phrase):
            if not _phrase_is_negated_in_sentence(each_sentence, each_phrase):
                return True
    return False


def _docstring_asserts_unconditional_break(docstring_text: str) -> bool:
    return _docstring_affirms_phrase(
        docstring_text, ALL_DOCSTRING_UNCONDITIONAL_BREAK_CLAIM_PHRASES
    )


def _docstring_asserts_fall_through(docstring_text: str) -> bool:
    return _docstring_affirms_phrase(
        docstring_text, ALL_DOCSTRING_FALL_THROUGH_CLAIM_PHRASES
    )


def _loop_control_flow_claim_issues(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    docstring_text = _function_docstring_text(function_node)
    if not _loop_bodies(function_node):
        return []
    contradictions: list[str] = []
    if _docstring_asserts_unconditional_break(docstring_text) and not (
        _any_loop_has_unconditional_break(function_node)
    ):
        contradictions.append(
            f"Line {function_node.lineno}: {function_node.name}() docstring claims it "
            "'breaks out of each loop' the moment a step runs, but every loop break is "
            "conditional — describe the actual condition that ends the loop"
        )
    if _docstring_asserts_fall_through(docstring_text) and not (
        _function_loops_have_skip_path(function_node)
    ):
        contradictions.append(
            f"Line {function_node.lineno}: {function_node.name}() docstring claims a loop "
            "will 'fall through' to the next entry, but every loop processes each entry with "
            "no skip path — describe the actual control flow"
        )
    return contradictions


def check_docstring_loop_control_flow_claims(content: str, file_path: str) -> list[str]:
    """Flag docstrings whose loop control-flow claims contradict the code.

    A docstring that asserts a function "breaks out of each loop the moment" a
    step runs, or that on a failure the loop "falls through to the next entry",
    is making a checkable claim. A claim phrase only counts as asserted when it
    appears affirmatively: a negation token (``not``, ``never``, ``does not``,
    ``will not``, and the like) before the phrase in the same sentence states
    the opposite, so the docstring is accurate and is left alone. The
    unconditional-break claim is false when every loop break is conditional —
    guarded by an ``if`` test, sitting under a guarded ``case``, or living in an
    ``except`` handler; a break under a wildcard ``case _:`` counts as
    unconditional. The fall-through claim is false only when every loop body
    runs each entry straight through with no skip path inside that body: no
    ``continue``, no ``if``, and no ``match`` within the loop. A skip path that
    sits before, after, or beside the loop does not satisfy the claim. Both
    phrasings drift out of sync with the body after a refactor and mislead the
    next reader, so each contradiction is reported.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per contradicted loop control-flow claim, capped at the
        module limit.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_private_or_dunder(each_node.name):
            continue
        if _function_has_exempt_decorator(each_node):
            continue
        if _function_body_line_count(each_node) <= DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT:
            continue
        issues.extend(_loop_control_flow_claim_issues(each_node))
        if len(issues) >= MAX_DOCSTRING_LOOP_CONTROL_FLOW_ISSUES:
            return issues[:MAX_DOCSTRING_LOOP_CONTROL_FLOW_ISSUES]
    return issues[:MAX_DOCSTRING_LOOP_CONTROL_FLOW_ISSUES]


def _function_docstring_text(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    docstring_value = ast.get_docstring(function_node)
    return docstring_value or ""


def _missing_docstring_sections(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    docstring_text = _function_docstring_text(function_node)
    documentable_parameter_count = _function_documentable_parameter_count(function_node)
    has_non_none_return = (
        function_node.returns is not None
        and not _annotation_is_explicit_none_return(function_node.returns)
        and not _annotation_is_noreturn(function_node.returns)
    )
    has_raise_statement = _function_body_contains_raise(function_node)
    has_yield_statement = _function_body_contains_yield(function_node)
    missing_sections: list[str] = []
    if documentable_parameter_count > 0 and "Args:" not in docstring_text:
        missing_sections.append("Args:")
    if has_non_none_return and not (
        "Returns:" in docstring_text or "Yields:" in docstring_text
    ):
        section_label = "Yields:" if has_yield_statement else "Returns:"
        missing_sections.append(section_label)
    if has_raise_statement and "Raises:" not in docstring_text:
        missing_sections.append("Raises:")
    return missing_sections


def check_docstring_format(content: str, file_path: str) -> list[str]:
    """Flag public functions missing required Google-style docstring sections.

    A public function whose signature has documentable parameters, returns
    a non-None value, or raises must have the matching `Args:` / `Returns:`
    (or `Yields:`) / `Raises:` sections so callers can read the contract
    without scanning the body.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_private_or_dunder(each_node.name):
            continue
        if _function_has_exempt_decorator(each_node):
            continue
        if _function_body_line_count(each_node) <= DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT:
            continue
        missing_sections = _missing_docstring_sections(each_node)
        if not missing_sections:
            continue
        issues.append(
            f"Line {each_node.lineno}: {each_node.name}() docstring missing required "
            f"section(s): {', '.join(missing_sections)} — Google style required for public APIs"
        )
        if len(issues) >= MAX_DOCSTRING_FORMAT_ISSUES:
            break
    return issues[:MAX_DOCSTRING_FORMAT_ISSUES]


def _signature_parameter_names(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    arguments = function_node.args
    real_names: set[str] = set()
    for each_argument in arguments.posonlyargs + arguments.args + arguments.kwonlyargs:
        real_names.add(each_argument.arg)
    if arguments.vararg is not None:
        real_names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        real_names.add(arguments.kwarg.arg)
    return real_names - ALL_SELF_AND_CLS_PARAMETER_NAMES


def _is_docstring_terminating_section_header(stripped_line: str) -> bool:
    return stripped_line in ALL_DOCSTRING_TERMINATING_SECTION_HEADERS


def _documented_argument_names(docstring_text: str) -> list[str]:
    docstring_lines = docstring_text.splitlines()
    args_section_index = _find_args_section_index(docstring_lines)
    if args_section_index is None:
        return []
    documented_names: list[str] = []
    entry_indent: int | None = None
    for each_line in docstring_lines[args_section_index + 1:]:
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        if _is_docstring_terminating_section_header(stripped_line):
            break
        current_indent = len(each_line) - len(each_line.lstrip())
        if current_indent == 0:
            break
        if entry_indent is None:
            entry_indent = current_indent
        if current_indent > entry_indent:
            continue
        entry_match = DOCSTRING_ARG_ENTRY_PATTERN.match(stripped_line)
        if entry_match is not None:
            documented_names.append(entry_match.group(1))
    return documented_names


def _find_args_section_index(all_docstring_lines: list[str]) -> int | None:
    for each_line_index, each_line in enumerate(all_docstring_lines):
        if each_line.strip() in ALL_DOCSTRING_ARGS_SECTION_HEADERS:
            return each_line_index
    return None


def check_docstring_args_match_signature(content: str, file_path: str) -> list[str]:
    """Flag docstring Args: entries naming a parameter the signature lacks.

    A fix that renames a parameter often leaves the adjacent ``Args:`` line
    stale. Each documented argument name is compared to the real signature;
    a documented name with no matching parameter is reported. Only the
    ``Args:`` section is validated — ``Raises:`` is left alone because
    callee-propagated exceptions cause false positives. Functions that
    accept ``**kwargs`` are skipped because their documented names may be
    keyword keys the signature cannot enumerate.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per stale documented argument, capped at the module limit.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_private_or_dunder(each_node.name):
            continue
        if _function_has_exempt_decorator(each_node):
            continue
        if _function_body_line_count(each_node) <= DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT:
            continue
        if each_node.args.kwarg is not None:
            continue
        documented_names = _documented_argument_names(_function_docstring_text(each_node))
        if not documented_names:
            continue
        real_names = _signature_parameter_names(each_node)
        for each_documented_name in documented_names:
            if each_documented_name in real_names:
                continue
            issues.append(
                f"Line {each_node.lineno}: {each_node.name}() docstring Args: lists "
                f"'{each_documented_name}' which is not a parameter - update the "
                "docstring to match the signature"
            )
            if len(issues) >= MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES:
                return issues[:MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES]
    return issues[:MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES]
