"""Magic value detection validator.

Implements check 7: No hardcoded magic values.
Use named constants instead of magic numbers.

Note: Only checks for magic numbers. Magic string detection is not implemented.
"""

import ast
import sys
from pathlib import Path
from typing import Dict, FrozenSet, List, Set

from validator_base import Violation


ALLOWED_NUMBERS: FrozenSet[int] = frozenset({-1, 0, 1})


def check_magic_values(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []
    negated_literal_ids: Set[int] = set()
    parent_by_child_id = _build_parent_map(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            operand = node.operand
            if isinstance(operand, ast.UnaryOp):
                continue
            if isinstance(operand, ast.Constant) and isinstance(operand.value, int):
                negated_literal_ids.add(id(operand))
                outermost_unary = _walk_up_unary_minus(node, parent_by_child_id)
                negation_depth = _count_unary_minus_depth(outermost_unary)
                unsigned_value = operand.value
                signed_value = -unsigned_value if negation_depth % 2 == 1 else unsigned_value
                if signed_value in ALLOWED_NUMBERS:
                    continue
                if _is_in_constant_definition(outermost_unary, parent_by_child_id):
                    continue
                violations.append(
                    Violation(
                        filename,
                        node.lineno,
                        f"Magic number {signed_value} - use named constant",
                    )
                )
            continue
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, int):
                continue
            if id(node) in negated_literal_ids:
                continue
            if node.value in ALLOWED_NUMBERS:
                continue
            if _is_in_constant_definition(node, parent_by_child_id):
                continue
            violations.append(
                Violation(
                    filename,
                    node.lineno,
                    f"Magic number {node.value} - use named constant",
                )
            )

    return violations


def _build_parent_map(tree: ast.AST) -> Dict[int, ast.AST]:
    parent_by_child_id: Dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_by_child_id[id(child)] = parent
    return parent_by_child_id


def _walk_up_unary_minus(
    node: ast.UnaryOp,
    parent_by_child_id: Dict[int, ast.AST],
) -> ast.UnaryOp:
    current: ast.UnaryOp = node
    while True:
        parent = parent_by_child_id.get(id(current))
        if isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.USub):
            current = parent
            continue
        return current


def _count_unary_minus_depth(node: ast.UnaryOp) -> int:
    depth = 0
    current: ast.AST = node
    while isinstance(current, ast.UnaryOp) and isinstance(current.op, ast.USub):
        depth += 1
        current = current.operand
    return depth


def _is_in_constant_definition(
    node: ast.AST,
    parent_by_child_id: Dict[int, ast.AST],
) -> bool:
    parent = parent_by_child_id.get(id(node))
    if isinstance(parent, ast.Assign):
        for target in parent.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                if parent.value is node:
                    return True
        return False
    if isinstance(parent, ast.AnnAssign):
        return (
            isinstance(parent.target, ast.Name)
            and parent.target.id.isupper()
            and parent.value is node
        )
    return False


def validate_file(file_path: Path) -> List[Violation]:
    filename = str(file_path)
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as error:
        return [Violation(filename, 0, f"Error: {error}")]

    return check_magic_values(tree, filename)


def main() -> int:
    if len(sys.argv) < 2:
        return 1

    all_violations: List[Violation] = []
    for file_arg in sys.argv[1:]:
        all_violations.extend(validate_file(Path(file_arg)))

    for violation in all_violations:
        print(violation)

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
