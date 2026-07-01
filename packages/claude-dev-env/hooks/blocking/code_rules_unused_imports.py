"""Unused module-level import check and its import-range and type-checking-gate helpers."""

import ast
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_scope_binding import (  # noqa: E402
    _attribute_root_name_if_loaded,
    _collect_string_annotation_names,
    _load_name_is_shadowed,
)
from code_rules_shared import (  # noqa: E402
    _build_parent_map,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.unused_module_import_constants import (  # noqa: E402
    ALL_TYPING_MODULE_NAMES,
    MAX_UNUSED_IMPORT_ISSUES,
    TYPE_CHECKING_IDENTIFIER,
    UNUSED_IMPORT_GUIDANCE,
    line_suppresses_unused_import_via_noqa,
)


def _import_alias_pairs(
    import_node: ast.Import | ast.ImportFrom,
) -> list[tuple[str, int, int | None]]:
    """Return (binding_name, alias_line, from_keyword_line) for each name introduced.

    The from-keyword line is None for plain `import X` statements; for
    `from X import (...)` it carries the line of the `from` keyword so
    callers can honor a `# noqa` placed on the opening line of a
    multi-line import block.
    """
    bindings: list[tuple[str, int, int | None]] = []
    from_keyword_line = import_node.lineno if isinstance(import_node, ast.ImportFrom) else None
    for each_alias in import_node.names:
        if each_alias.name == "*":
            continue
        binding_name = each_alias.asname if each_alias.asname else each_alias.name.split(".")[0]
        alias_line = each_alias.lineno or import_node.lineno
        bindings.append((binding_name, alias_line, from_keyword_line))
    return bindings


def _import_statement_line_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for each_node in tree.body:
        if isinstance(each_node, (ast.Import, ast.ImportFrom)):
            start_line = each_node.lineno
            end_line = each_node.end_lineno or each_node.lineno
            ranges.append((start_line, end_line))
    return ranges


def _line_number_falls_in_import_ranges(
    line_number: int,
    all_import_line_ranges: list[tuple[int, int]],
) -> bool:
    for each_start, each_end in all_import_line_ranges:
        if each_start <= line_number <= each_end:
            return True
    return False


def _type_checking_guard_aliases(tree: ast.Module) -> tuple[set[str], set[str]]:
    all_type_checking_names = {TYPE_CHECKING_IDENTIFIER}
    all_type_checking_module_aliases = set(ALL_TYPING_MODULE_NAMES)
    for each_statement in tree.body:
        if isinstance(each_statement, ast.Import):
            for each_alias in each_statement.names:
                if each_alias.name in ALL_TYPING_MODULE_NAMES:
                    all_type_checking_module_aliases.add(
                        each_alias.asname or each_alias.name
                    )
        elif isinstance(each_statement, ast.ImportFrom):
            if each_statement.module not in ALL_TYPING_MODULE_NAMES:
                continue
            for each_alias in each_statement.names:
                if each_alias.name == TYPE_CHECKING_IDENTIFIER:
                    all_type_checking_names.add(each_alias.asname or each_alias.name)
    return all_type_checking_names, all_type_checking_module_aliases


def _expression_guards_type_checking_block(
    test_expression: ast.expr,
    all_type_checking_names: set[str],
    all_type_checking_module_aliases: set[str],
) -> bool:
    if isinstance(test_expression, ast.Name):
        return test_expression.id in all_type_checking_names
    if isinstance(test_expression, ast.Attribute):
        if test_expression.attr != TYPE_CHECKING_IDENTIFIER:
            return False
        receiver = test_expression.value
        return (
            isinstance(receiver, ast.Name)
            and receiver.id in all_type_checking_module_aliases
        )
    return False


def _module_body_declares_type_checking_gate(tree: ast.Module) -> bool:
    (
        all_type_checking_names,
        all_type_checking_module_aliases,
    ) = _type_checking_guard_aliases(tree)
    return any(
        isinstance(each_statement, ast.If)
        and _expression_guards_type_checking_block(
            each_statement.test,
            all_type_checking_names,
            all_type_checking_module_aliases,
        )
        for each_statement in tree.body
    )


def _collect_load_names_outside_import_ranges(
    tree: ast.Module,
    all_import_line_ranges: list[tuple[int, int]],
) -> set[str]:
    parent_by_node_id = _build_parent_map(tree)
    referenced_names: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Name) and isinstance(each_node.ctx, ast.Load):
            line_number = each_node.lineno
            if line_number is None or _line_number_falls_in_import_ranges(
                line_number,
                all_import_line_ranges,
            ):
                continue
            if _load_name_is_shadowed(each_node, each_node.id, parent_by_node_id):
                continue
            referenced_names.add(each_node.id)
        elif isinstance(each_node, ast.Attribute) and isinstance(
            each_node.ctx, ast.Load
        ):
            line_number = each_node.lineno
            if line_number is None or _line_number_falls_in_import_ranges(
                line_number,
                all_import_line_ranges,
            ):
                continue
            root_name = _attribute_root_name_if_loaded(each_node)
            if root_name is not None and not _load_name_is_shadowed(
                root_name,
                root_name.id,
                parent_by_node_id,
            ):
                referenced_names.add(root_name.id)
    referenced_names.update(_collect_string_annotation_names(tree))
    return referenced_names


def _module_declares_dunder_all(tree: ast.Module) -> bool:
    """Return True when the module body assigns or annotates ``__all__``."""
    return any(
        (
            isinstance(each_node, ast.Assign)
            and any(
                isinstance(each_target, ast.Name) and each_target.id == "__all__"
                for each_target in each_node.targets
            )
        )
        or (
            isinstance(each_node, ast.AnnAssign)
            and isinstance(each_node.target, ast.Name)
            and each_node.target.id == "__all__"
        )
        for each_node in tree.body
    )


def _module_level_import_bindings(
    tree: ast.Module,
) -> list[tuple[str, int, int | None]]:
    """Return (binding_name, alias_line, from_keyword_line) for each module-level import.

    ``from __future__`` imports are excluded: their binding names are never
    referenced, yet the import changes compilation behavior rather than being
    dead.
    """
    bindings: list[tuple[str, int, int | None]] = []
    for each_node in tree.body:
        if not isinstance(each_node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(each_node, ast.ImportFrom) and each_node.module == "__future__":
            continue
        bindings.extend(_import_alias_pairs(each_node))
    return bindings


def _referenced_names_in_tree(tree: ast.Module) -> set[str]:
    """Return every name loaded outside the module's own import statements."""
    import_ranges = _import_statement_line_ranges(tree)
    return _collect_load_names_outside_import_ranges(tree, import_ranges)


def _import_line_is_noqa_suppressed(
    all_source_lines: list[str],
    alias_line: int,
    from_keyword_line: int | None,
) -> bool:
    """Return True when a bare ``# noqa`` or an ``F401`` noqa sits on the import.

    The alias line and, for a ``from X import (...)`` block, the ``from``
    keyword line both suppress, mirroring where an author places the directive.
    """
    if 1 <= alias_line <= len(all_source_lines):
        if line_suppresses_unused_import_via_noqa(all_source_lines[alias_line - 1]):
            return True
    if from_keyword_line is not None and 1 <= from_keyword_line <= len(all_source_lines):
        if line_suppresses_unused_import_via_noqa(all_source_lines[from_keyword_line - 1]):
            return True
    return False


def _orphaned_import_issues(
    post_edit_tree: ast.Module,
    all_post_edit_lines: list[str],
    all_post_edit_referenced_names: set[str],
    prior_full_file_content: str,
    all_flagged_names: set[str],
    remaining_capacity: int,
) -> list[str]:
    """Flag a post-edit import whose last reference this edit removed.

    An import present in the post-edit file, unused there, yet referenced in the
    prior file was orphaned by this edit: the edit deleted its last consumer
    while leaving the import line in place — the blind spot the fragment-only
    scan misses, because the orphaned import line sits outside the edited
    fragment. A pre-existing unused import the edit never touched stays
    unflagged: it was already unused in the prior file, so its name is absent
    from the prior references too, and this pass keys on prior use. Line numbers
    and ``# noqa`` suppression read from the post-edit file, where the import
    line lives.
    """
    if remaining_capacity <= 0:
        return []
    try:
        prior_tree = ast.parse(prior_full_file_content)
    except SyntaxError:
        return []
    prior_referenced_names = _referenced_names_in_tree(prior_tree)
    issues: list[str] = []
    for each_name, each_line_number, each_from_keyword_line in (
        _module_level_import_bindings(post_edit_tree)
    ):
        if each_name in all_flagged_names:
            continue
        if each_name in all_post_edit_referenced_names:
            continue
        if each_name not in prior_referenced_names:
            continue
        if _import_line_is_noqa_suppressed(
            all_post_edit_lines, each_line_number, each_from_keyword_line
        ):
            continue
        issues.append(
            f"Line {each_line_number}: unused module-level import {each_name!r}"
            f" — {UNUSED_IMPORT_GUIDANCE}"
        )
        all_flagged_names.add(each_name)
        if len(issues) >= remaining_capacity:
            break
    return issues


def _fragment_import_issues(
    content: str,
    all_referenced_names: set[str],
    all_flagged_names: set[str],
) -> list[str]:
    """Flag imports the edit fragment introduces that the post-edit file never uses.

    An Edit fragment taken from inside a function body does not parse as a
    module. It carries no module-level import to flag, so the empty list it
    yields lets the orphaned-import pass still run against the full file.
    """
    try:
        fragment_tree = ast.parse(content)
    except SyntaxError:
        return []
    fragment_lines = content.splitlines()
    issues: list[str] = []
    for each_name, each_line_number, each_from_keyword_line in (
        _module_level_import_bindings(fragment_tree)
    ):
        if _import_line_is_noqa_suppressed(
            fragment_lines, each_line_number, each_from_keyword_line
        ):
            continue
        if each_name in all_referenced_names:
            continue
        issues.append(
            f"Line {each_line_number}: unused module-level import {each_name!r}"
            f" — {UNUSED_IMPORT_GUIDANCE}"
        )
        all_flagged_names.add(each_name)
        if len(issues) >= MAX_UNUSED_IMPORT_ISSUES:
            break
    return issues


def check_unused_module_level_imports(
    content: str,
    file_path: str,
    full_file_content: str | None = None,
    prior_full_file_content: str | None = None,
) -> list[str]:
    """Flag module-level imports that are never referenced in the rest of the file.

    References are detected from AST ``Name`` / ``Attribute`` loads outside import
    statements so mentions in comments or string literals do not count. Files
    declaring ``__all__`` (including annotated assignments) are skipped. Files
    whose module body includes ``if TYPE_CHECKING:`` (or
    ``typing[._extensions].TYPE_CHECKING``) are skipped. Suppression honors bare
    ``# noqa`` or an explicit ``F401`` code in the noqa list only.

    When ``full_file_content`` is provided, ``content`` is treated as an Edit
    fragment containing the imports being added or replaced, while the
    ``__all__`` / ``TYPE_CHECKING`` gate detection and reference scanning run
    against ``full_file_content`` (the post-edit file as it will look once the
    Edit applies). This prevents false-positive flags on imports added in the
    same Edit as their consumers.

    When both ``full_file_content`` and ``prior_full_file_content`` are provided
    (the Edit case), a second pass flags a post-edit import the edit orphaned —
    unused in the post-edit file, yet referenced in the prior file, so the edit
    deleted its last consumer while leaving the import line, which sits outside
    the fragment. A pre-existing unused import the edit never touched stays
    unflagged, since it was already unused in the prior file.
    """
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    reference_source = full_file_content if full_file_content is not None else content
    try:
        reference_tree = ast.parse(reference_source)
    except SyntaxError:
        return []
    if _module_declares_dunder_all(reference_tree):
        return []
    if _module_body_declares_type_checking_gate(reference_tree):
        return []
    referenced_names = _referenced_names_in_tree(reference_tree)
    flagged_names: set[str] = set()
    issues = _fragment_import_issues(content, referenced_names, flagged_names)
    if full_file_content is not None and prior_full_file_content:
        issues.extend(
            _orphaned_import_issues(
                reference_tree,
                reference_source.splitlines(),
                referenced_names,
                prior_full_file_content,
                flagged_names,
                MAX_UNUSED_IMPORT_ISSUES - len(issues),
            )
        )
    return issues
