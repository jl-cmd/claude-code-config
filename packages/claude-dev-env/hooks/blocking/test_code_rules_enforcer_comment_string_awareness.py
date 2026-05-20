"""Tests pinning string-aware ``#`` detection in the Python comment checks.

``#`` characters appear inside string literals in three common shapes:
hex color codes (``"#FFFFFF"``), URL fragments
(``"https://x#section"``), and f-string interpolation patterns. None of
those ``#`` characters belong to a comment token. ``check_comments_python``
and the Python branch of ``extract_comment_texts`` route their ``#``
detection through ``tokenize.generate_tokens`` so only true ``COMMENT``
tokens are considered. These tests pin both halves of that contract:
``#``-in-strings is exempt; real inline comments that land AFTER such
a string still flag.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def test_python_check_should_not_flag_hex_color_literal() -> None:
    content = 'palette_primary = "#FFFFFF"\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == []


def test_python_check_should_not_flag_url_fragment_in_string() -> None:
    content = 'docs_link = "https://example.com/guide#installation"\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == []


def test_python_check_should_not_flag_hash_inside_fstring_interpolation() -> None:
    content = 'rendered = f"prefix #{count} suffix"\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == []


def test_python_check_should_not_flag_hash_inside_triple_quoted_string() -> None:
    content = 'message = """use # for inline comments"""\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert issues == []


def test_python_check_should_flag_real_inline_comment_after_string_with_hash() -> None:
    content = 'name = "user"  # this comment must still flag\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert len(issues) == 1
    assert "Comment found" in issues[0]


def test_python_check_should_flag_real_comment_after_hex_color_literal() -> None:
    content = 'palette_primary = "#FFFFFF"  # accidentally added comment\n'
    issues = code_rules_enforcer.check_comments_python(content)
    assert len(issues) == 1
    assert "Comment found" in issues[0]


def test_extract_should_not_classify_hex_color_as_inline_comment() -> None:
    content = 'palette_primary = "#FFFFFF"\n'
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert inline == set()
    assert standalone == set()


def test_extract_should_classify_real_inline_comment_after_string_with_hash() -> None:
    content = 'name = "user"  # real comment\n'
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert len(inline) == 1
    assert "# real comment" in next(iter(inline))
    assert standalone == set()


def test_extract_should_classify_standalone_comment_correctly() -> None:
    content = "# standalone comment\nx = 1\n"
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert "# standalone comment" in standalone
    assert inline == set()


def test_extract_should_distinguish_inline_from_standalone_in_same_file() -> None:
    content = '# standalone first\nx = "#FFFFFF"  # inline real comment\n# standalone second\n'
    inline, standalone = code_rules_enforcer.extract_comment_texts(content, "foo.py")
    assert "# inline real comment" in next(iter(inline))
    assert "# standalone first" in standalone
    assert "# standalone second" in standalone
