"""Cross-file duplicate top-level function body detection.

The check flags a top-level function in the file being written whose body is
structurally identical to a top-level function already defined in a sibling
``.py`` module in the same directory. This catches the Reuse-before-create / DRY
violation where a helper is copy-pasted across several modules instead of being
imported from one shared home.

The scan is deliberately conservative to keep false positives near zero:

- Only module-scope ``def`` / ``async def`` bodies are compared (the copied-helper
  case), never methods nested in a class.
- Bodies are compared by their normalized AST structure, so reformatting,
  renamed local variables, and comment differences do not hide a copy, while two
  genuinely different functions never collide.
- A body must contain at least ``MINIMUM_DUPLICATE_BODY_STATEMENTS`` statements;
  trivial one- or two-line helpers (``return None``, a single delegation) are too
  common to flag.
- Test files and ``__init__.py`` re-export surfaces never participate, on either
  the writing side or the sibling side.

Unlike most code-rules checks, this one runs on hook-infrastructure files: the
copied-helper violation it targets appears most often in the ``blocking/`` hook
directory itself, so gating it behind the hook-infrastructure exemption would
leave the exact violation class unguarded.
"""

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
    is_test_file,
)

from hooks_constants.duplicate_function_body_constants import (  # noqa: E402
    DUNDER_INIT_FILENAME,
    DUPLICATE_BODY_GUIDANCE,
    MAX_DUPLICATE_BODY_ISSUES,
    MINIMUM_DUPLICATE_BODY_STATEMENTS,
    PYTHON_SOURCE_SUFFIX,
)


def _normalized_body_signature(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Return a position-independent structural fingerprint of the function body.

    The docstring statement, when present, is dropped so two copies that differ
    only in their docstring still collide. Returns None when the remaining body
    is shorter than the minimum statement count, which signals the caller to skip
    this function as too trivial to be a meaningful duplicate.

    Args:
        function_node: The module-scope function definition to fingerprint.

    Returns:
        A normalized AST dump of the body statements, or None when the body is
        too small to compare.
    """
    body_statements = list(function_node.body)
    if body_statements and isinstance(body_statements[0], ast.Expr):
        first_value = body_statements[0].value
        if isinstance(first_value, ast.Constant) and isinstance(first_value.value, str):
            body_statements = body_statements[1:]
    if len(body_statements) < MINIMUM_DUPLICATE_BODY_STATEMENTS:
        return None
    return "\n".join(
        ast.dump(each_statement, annotate_fields=False) for each_statement in body_statements
    )


def _top_level_function_signatures(tree: ast.Module) -> dict[str, str]:
    """Map each module-scope function name to its normalized body signature.

    Functions whose body is too trivial to compare are omitted.

    Args:
        tree: The parsed module.

    Returns:
        A name-to-signature mapping for the comparable top-level functions.
    """
    signature_by_name: dict[str, str] = {}
    for each_node in tree.body:
        if isinstance(each_node, ast.FunctionDef | ast.AsyncFunctionDef):
            body_signature = _normalized_body_signature(each_node)
            if body_signature is not None:
                signature_by_name[each_node.name] = body_signature
    return signature_by_name


def _is_comparable_sibling(sibling_path: Path, written_file_name: str) -> bool:
    """Return whether a directory entry is a sibling module worth comparing against.

    Args:
        sibling_path: A candidate path from the written file's directory.
        written_file_name: The base name of the file being written.

    Returns:
        True for a Python source file other than the written file itself,
        excluding ``__init__.py`` and test modules.
    """
    if not sibling_path.is_file():
        return False
    if sibling_path.suffix != PYTHON_SOURCE_SUFFIX:
        return False
    if sibling_path.name == written_file_name:
        return False
    if sibling_path.name == DUNDER_INIT_FILENAME:
        return False
    return not is_test_file(sibling_path.name)


def _sibling_signatures(file_path: str) -> dict[str, list[str]]:
    """Collect normalized body signatures from every comparable sibling module.

    Args:
        file_path: The path of the file being written.

    Returns:
        A signature-to-source-names mapping, where the value lists the
        ``module.py::function`` locations carrying that body.
    """
    written_path = Path(file_path)
    directory = written_path.parent
    source_names_by_signature: dict[str, list[str]] = {}
    try:
        all_entries = sorted(directory.iterdir())
    except OSError:
        return {}
    for each_entry in all_entries:
        if not _is_comparable_sibling(each_entry, written_path.name):
            continue
        try:
            sibling_source = each_entry.read_text(encoding="utf-8")
            sibling_tree = ast.parse(sibling_source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for each_name, each_signature in _top_level_function_signatures(sibling_tree).items():
            location = f"{each_entry.name}::{each_name}"
            source_names_by_signature.setdefault(each_signature, []).append(location)
    return source_names_by_signature


def check_duplicate_function_body_across_files(content: str, file_path: str) -> list[str]:
    """Flag top-level functions copied byte-for-structure from a sibling module.

    Compares each module-scope function in the post-edit content against the
    top-level functions of every comparable ``.py`` sibling in the same
    directory, and reports any whose normalized body matches. Test files and
    ``__init__.py`` are skipped on both sides.

    Args:
        content: The full post-edit file content being written.
        file_path: The destination path of the write.

    Returns:
        A list of human-readable violation strings, one per duplicated function.
    """
    written_name = Path(file_path).name
    if written_name == DUNDER_INIT_FILENAME:
        return []
    if is_test_file(file_path):
        return []
    try:
        written_tree = ast.parse(content)
    except SyntaxError:
        return []
    written_signatures = _top_level_function_signatures(written_tree)
    if not written_signatures:
        return []
    source_names_by_signature = _sibling_signatures(file_path)
    issues: list[str] = []
    for each_name, each_signature in written_signatures.items():
        matching_locations = source_names_by_signature.get(each_signature)
        if not matching_locations:
            continue
        first_location = matching_locations[0]
        issues.append(
            f"Function {each_name!r} duplicates {first_location} — {DUPLICATE_BODY_GUIDANCE}"
        )
        if len(issues) >= MAX_DUPLICATE_BODY_ISSUES:
            break
    return issues
