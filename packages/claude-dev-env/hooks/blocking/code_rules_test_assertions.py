"""Skip-decorator, existence-only, constant-equality, stale-renamed-name, and flag-gated scenario test-quality checks."""

import ast
import sys
from pathlib import Path

_SCENARIO_NAME_CLAUSES = ("_when_", "_passes", "_succeeds", "_on_clean")
_MINIMUM_SIBLING_PATCH_COUNT = 2

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_shared import (  # noqa: E402
    is_test_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    UPPER_SNAKE_CONSTANT_PATTERN,
)


def _decorator_name_contains_skip(decorator_node: ast.expr) -> bool:
    """Return True when a decorator AST node references an identifier containing 'skip'."""
    if isinstance(decorator_node, ast.Name):
        return "skip" in decorator_node.id.lower()
    if isinstance(decorator_node, ast.Attribute):
        return "skip" in decorator_node.attr.lower()
    if isinstance(decorator_node, ast.Call):
        return _decorator_name_contains_skip(decorator_node.func)
    return False


def check_skip_decorators_in_tests(content: str, file_path: str) -> list[str]:
    """Flag @skip decorators on test functions in test files.

    Tests must fail on missing dependencies rather than skip silently.
    Only applies to test files; production files are exempt.
    Only flags decorators applied to functions whose names start with 'test'.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        for each_decorator in each_node.decorator_list:
            if _decorator_name_contains_skip(each_decorator):
                issues.append(
                    f"Line {each_decorator.lineno}: @skip decorator on test"
                    f" — tests must fail on missing deps"
                )

    return issues


def _collect_assert_nodes_bounded(node: ast.AST) -> list[ast.Assert]:
    """Collect Assert nodes under node without crossing scope boundaries.

    Terminates descent at FunctionDef, AsyncFunctionDef, ClassDef, and Lambda
    nodes so that assertions belonging to nested scopes are not attributed to
    the enclosing function body.
    """
    scope_boundary_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    assertions: list[ast.Assert] = []
    nodes_to_visit: list[ast.AST] = list(ast.iter_child_nodes(node))
    while nodes_to_visit:
        current = nodes_to_visit.pop()
        if isinstance(current, ast.Assert):
            assertions.append(current)
        if isinstance(current, scope_boundary_types):
            continue
        nodes_to_visit.extend(ast.iter_child_nodes(current))
    return assertions


def _collect_body_assertions(statement_nodes: list[ast.stmt]) -> list[ast.Assert]:
    """Collect Assert nodes from a function body without descending into nested scopes."""
    assertions: list[ast.Assert] = []
    for each_stmt in statement_nodes:
        if isinstance(each_stmt, ast.Assert):
            assertions.append(each_stmt)
            continue
        if isinstance(each_stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        assertions.extend(_collect_assert_nodes_bounded(each_stmt))
    return assertions


def _is_existence_only_assertion(call_node: ast.Call) -> bool:
    """Return True when a Call node is callable() or hasattr()."""
    function_reference = call_node.func
    if isinstance(function_reference, ast.Name):
        return function_reference.id in ("callable", "hasattr")
    if isinstance(function_reference, ast.Attribute):
        return function_reference.attr in ("callable", "hasattr")
    return False


def _test_body_has_only_existence_assertions(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Return True when a test function body contains only existence-check assertions."""
    assertion_nodes = _collect_body_assertions(function_node.body)
    if not assertion_nodes:
        return False

    non_existence_assertions = 0
    for each_assert in assertion_nodes:
        test_expr = each_assert.test
        if isinstance(test_expr, ast.Call) and _is_existence_only_assertion(test_expr):
            continue
        if isinstance(test_expr, ast.Compare):
            comparators = test_expr.comparators
            ops = test_expr.ops
            if (
                len(ops) == 1
                and isinstance(ops[0], ast.IsNot)
                and len(comparators) == 1
                and isinstance(comparators[0], ast.Constant)
                and comparators[0].value is None
            ):
                continue
        non_existence_assertions += 1

    return non_existence_assertions == 0


def check_existence_check_tests(content: str, file_path: str) -> list[str]:
    """Flag test functions containing only existence-check assertions.

    Tests asserting only callable(x), hasattr(m, 'name'), or x is not None
    verify nothing about behavior. They should be deleted or replaced with
    assertions that exercise actual functionality.
    Only applies to test files.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        if _test_body_has_only_existence_assertions(each_node):
            issues.append(
                f"Line {each_node.lineno}: existence-check test"
                f" — delete or replace with a behavior test"
            )

    return issues


def _is_upper_snake_name(name: str) -> bool:
    """Return True when an identifier is written in UPPER_SNAKE_CASE."""
    return bool(UPPER_SNAKE_CONSTANT_PATTERN.match(name))


def _assert_is_constant_equality_only(assert_node: ast.Assert) -> bool:
    """Return True when the assertion compares an UPPER_SNAKE name to a literal."""
    test_expr = assert_node.test
    if not isinstance(test_expr, ast.Compare):
        return False
    if len(test_expr.ops) != 1 or not isinstance(test_expr.ops[0], ast.Eq):
        return False
    left = test_expr.left
    right = test_expr.comparators[0]
    is_left_upper_snake = isinstance(left, ast.Name) and _is_upper_snake_name(left.id)
    is_right_upper_snake = isinstance(right, ast.Name) and _is_upper_snake_name(right.id)
    if is_left_upper_snake and is_right_upper_snake:
        return False
    is_left_a_literal = isinstance(left, ast.Constant)
    is_right_a_literal = isinstance(right, ast.Constant)
    return (
        (is_left_upper_snake and is_right_a_literal)
        or (is_right_upper_snake and is_left_a_literal)
    )


def check_constant_equality_tests(content: str, file_path: str) -> list[str]:
    """Flag test functions whose sole assertion compares a constant to a literal.

    Tests like 'assert CACHE_DIR == "cache"' cover no behavior — they just
    verify the constant has not changed. Such tests should be deleted.
    Only applies to test files; production files are exempt.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        all_assertions = _collect_body_assertions(each_node.body)
        if not all_assertions:
            continue
        if len(all_assertions) > 1:
            continue
        if _assert_is_constant_equality_only(all_assertions[0]):
            issues.append(
                f"Line {each_node.lineno}: constant-value test"
                f" — delete; tests must cover behavior"
            )

    return issues


def _collect_referenced_symbol_names(module_tree: ast.Module) -> set[str]:
    """Return every callable-shaped name the module imports, defines, or references.

    A name counts as referenced when it is imported (``import``/``from import``,
    honoring the bound alias), defined as a top-level function or class, used as a
    direct call target (``name(...)``), or read anywhere as an ``ast.Name`` load.
    The union is the set of symbols that still live in the file, so a token absent
    from it names a symbol the file no longer references.
    """
    referenced_names: set[str] = set()
    for each_node in ast.walk(module_tree):
        if isinstance(each_node, ast.Import):
            for each_alias in each_node.names:
                referenced_names.add(each_alias.asname or each_alias.name.split(".", 1)[0])
        elif isinstance(each_node, ast.ImportFrom):
            for each_alias in each_node.names:
                referenced_names.add(each_alias.asname or each_alias.name)
        elif isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            referenced_names.add(each_node.name)
        elif isinstance(each_node, ast.Name):
            referenced_names.add(each_node.id)
        elif isinstance(each_node, ast.Attribute):
            referenced_names.add(each_node.attr)
    return referenced_names


def _direct_call_names_in_body(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    """Return the names of every direct ``name(...)`` call inside a function body."""
    called_names: set[str] = set()
    for each_node in ast.walk(function_node):
        if isinstance(each_node, ast.Call) and isinstance(each_node.func, ast.Name):
            called_names.add(each_node.func.id)
    return called_names


_MINIMUM_SHARED_PREFIX_SEGMENTS = 2


def _stale_renamed_token_in_test_name(
    test_name: str,
    called_name: str,
    referenced_names: set[str],
) -> str | None:
    """Return a stale renamed-symbol token a test name carries, or None.

    A called function ``called_name`` of two or more snake_case segments names the
    symbol the test exercises. A genuine rename leaves behind a sibling token of the
    same segment count, sharing the called function's leading segments and final
    segment while differing in a middle segment. The prefix-anchored token of that
    exact segment count inside the test name is the sibling candidate; the test
    carries a stale token when that candidate differs from the called name in a
    middle segment and is referenced nowhere in the file. A candidate equal to the
    called name or still referenced clears the test, so a name that names its
    function — or embeds a token the file still imports — does not flag. A token of
    a different segment count (an added or dropped word, such as a descriptive
    abbreviation) is not a rename sibling and clears the test. That stale token is
    the signature of an incomplete rename: the call site moved to the new name
    while the test identifier kept the old one.

    Args:
        test_name: The ``test_*`` function identifier under inspection.
        called_name: A direct-call target inside that test's body.
        referenced_names: Every name the module imports, defines, or references.

    Returns:
        The stale token embedded in the test name, or None when none is present.
    """
    called_segments = called_name.split("_")
    if len(called_segments) < _MINIMUM_SHARED_PREFIX_SEGMENTS:
        return None
    if called_name in test_name:
        return None
    shared_prefix = "_".join(called_segments[:_MINIMUM_SHARED_PREFIX_SEGMENTS]) + "_"
    prefix_start = test_name.find(shared_prefix)
    if prefix_start == -1:
        return None
    token_remainder = test_name[prefix_start:]
    token_segments = token_remainder.split("_")
    if len(token_segments) < len(called_segments):
        return None
    candidate_segments = token_segments[: len(called_segments)]
    if candidate_segments[-1] != called_segments[-1]:
        return None
    candidate_token = "_".join(candidate_segments)
    if candidate_token == called_name:
        return None
    if candidate_token in referenced_names:
        return None
    return candidate_token


def check_stale_renamed_symbol_in_test_name(content: str, file_path: str) -> list[str]:
    """Flag a test whose name embeds a renamed symbol the file no longer references.

    After a production function is renamed, its import, call site, and docstrings
    move to the new name, but a test function identifier can keep the old token —
    ``test_collect_skip_theme_names_keeps_only_x`` still calls the renamed
    ``collect_skip_clean_names``. The stale token names a symbol that exists nowhere
    in the file, so the test name no longer names the function it exercises. This
    check fires when a test calls a multi-segment function, embeds a same-length
    sibling token that shares the called function's leading segments and final
    segment but differs in a middle segment, and that embedded token is referenced
    nowhere in the file. A test whose name contains any function it calls is exempt:
    the name already names a function it exercises, so a sibling token derived from
    a different call is coincidental, not a stale rename. Only applies to test files;
    production files are exempt.

    Args:
        content: The file body under validation.
        file_path: Path to the file, used for the test-file gate.

    Returns:
        A list of issue strings, one per stale-token test name found.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    referenced_names = _collect_referenced_symbol_names(syntax_tree)
    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        all_called_names = _direct_call_names_in_body(each_node)
        if any(each_call in each_node.name for each_call in all_called_names):
            continue
        for each_called_name in sorted(all_called_names):
            stale_token = _stale_renamed_token_in_test_name(
                each_node.name, each_called_name, referenced_names
            )
            if stale_token is not None:
                issues.append(
                    f"Line {each_node.lineno}: test name {each_node.name!r} embeds"
                    f" {stale_token!r}, a symbol the file no longer references;"
                    f" the test calls {each_called_name!r}. Rename the test to match"
                    f" the function it exercises."
                )
                break

    return issues


def _flag_symbol_from_setattr_target(target_node: ast.expr) -> str | None:
    """Return the UPPER_SNAKE flag symbol a monkeypatch.setattr target names.

    Accepts both target shapes monkeypatch.setattr supports: a dotted string
    path (``"pkg.module.FLAG"``) and an attribute access (``module.FLAG``). The
    flag is the final dotted segment when that segment is UPPER_SNAKE_CASE; any
    other segment shape returns None so only module-level boolean flags qualify.

    Args:
        target_node: The first positional argument of a ``monkeypatch.setattr``
            call.

    Returns:
        The UPPER_SNAKE flag name, or None when the target names no such symbol.
    """
    if isinstance(target_node, ast.Constant) and isinstance(target_node.value, str):
        final_segment = target_node.value.rsplit(".", 1)[-1]
        return final_segment if _is_upper_snake_name(final_segment) else None
    if isinstance(target_node, ast.Attribute):
        return target_node.attr if _is_upper_snake_name(target_node.attr) else None
    return None


def _is_monkeypatch_setattr(call_node: ast.Call) -> bool:
    """Return True when a Call node is a ``monkeypatch.setattr(...)`` invocation."""
    function_reference = call_node.func
    return (
        isinstance(function_reference, ast.Attribute)
        and function_reference.attr == "setattr"
        and isinstance(function_reference.value, ast.Name)
        and function_reference.value.id == "monkeypatch"
    )


def _flags_patched_in_test(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Return the set of UPPER_SNAKE flag symbols a test patches via monkeypatch.setattr."""
    patched_flags: set[str] = set()
    for each_node in ast.walk(function_node):
        if not isinstance(each_node, ast.Call):
            continue
        if not _is_monkeypatch_setattr(each_node) or not each_node.args:
            continue
        flag_symbol = _flag_symbol_from_setattr_target(each_node.args[0])
        if flag_symbol is not None:
            patched_flags.add(flag_symbol)
    return patched_flags


def _name_encodes_scenario(test_name: str) -> bool:
    """Return True when a test name carries a scenario clause asserting a condition."""
    return any(each_clause in test_name for each_clause in _SCENARIO_NAME_CLAUSES)


def check_flag_gated_scenario_test_naming(content: str, file_path: str) -> list[str]:
    """Flag a scenario-named test that omits a flag its siblings establish.

    When two or more sibling tests in a file monkeypatch the same module-level
    UPPER_SNAKE flag, that flag governs which branch the code under test runs.
    A test whose name asserts a scenario (``_when_``, ``_passes``, ``_succeeds``,
    ``_on_clean``) but never patches that flag runs under the flag's default
    value, so its named condition may not be in effect — the audit category N
    test-name-scenario mismatch. Advisory only; emitted to stderr, never blocks.
    Only applies to test files; production files are exempt.

    Args:
        content: The file body under validation.
        file_path: Path to the file, used for the test-file gate.

    Returns:
        An empty list; advisories print to stderr so the write proceeds.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    test_functions = [
        each_node
        for each_node in ast.walk(syntax_tree)
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and each_node.name.startswith("test")
    ]
    flags_patched_by_test = {
        each_test.name: _flags_patched_in_test(each_test) for each_test in test_functions
    }
    sibling_patch_count_by_flag: dict[str, int] = {}
    for patched_flags in flags_patched_by_test.values():
        for each_flag in patched_flags:
            sibling_patch_count_by_flag[each_flag] = (
                sibling_patch_count_by_flag.get(each_flag, 0) + 1
            )
    established_flags = {
        each_flag
        for each_flag, patch_count in sibling_patch_count_by_flag.items()
        if patch_count >= _MINIMUM_SIBLING_PATCH_COUNT
    }
    if not established_flags:
        return []

    for each_test in test_functions:
        if not _name_encodes_scenario(each_test.name):
            continue
        unpatched_flags = established_flags - flags_patched_by_test[each_test.name]
        if unpatched_flags:
            flag_list = ", ".join(sorted(unpatched_flags))
            print(
                f"ADVISORY [CODE_RULES] Line {each_test.lineno}: scenario test"
                f" {each_test.name!r} never patches {flag_list}, which sibling tests"
                f" establish — the named scenario may run under the flag default."
                f" Patch the flag (and assert the gated path runs) or rename the test.",
                file=sys.stderr,
            )

    return []
