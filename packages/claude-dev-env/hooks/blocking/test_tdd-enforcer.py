"""Hyphen-stem alias for test_tdd_enforcer.

The TDD enforcer currently only looks for sibling tests whose stem matches
the production file exactly, including any hyphens. Until the hook is
updated to also try a snake_cased stem variant, this alias file exists so
edits to tdd-enforcer.py can still find a matching test. Once the snake_case
fallback ships, this file can be removed.
"""

from test_tdd_enforcer import *  # noqa: F401,F403


def test_alias_reexports_snake_cased_test_module() -> None:
    import test_tdd_enforcer as snake_cased_test_module

    assert hasattr(
        snake_cased_test_module,
        "test_should_allow_when_hyphenated_production_has_snake_cased_sibling_test",
    )
