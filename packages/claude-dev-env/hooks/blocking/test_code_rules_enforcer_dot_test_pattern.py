"""Regression tests for .test.{ts,tsx,js} recognition in code-rules-enforcer."""

import importlib.util
import pathlib


def _load_enforcer_module():
    enforcer_path = pathlib.Path(__file__).parent / "code-rules-enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", enforcer_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


enforcer = _load_enforcer_module()


def test_is_test_file_should_recognize_dot_test_tsx_files():
    assert enforcer.is_test_file("C:/foo/Button.test.tsx") is True


def test_is_test_file_should_recognize_dot_test_ts_files():
    assert enforcer.is_test_file("C:/foo/Button.test.ts") is True


def test_is_test_file_should_recognize_dot_test_js_files():
    assert enforcer.is_test_file("C:/foo/Button.test.js") is True


def test_is_test_file_should_still_recognize_python_test_files():
    assert enforcer.is_test_file("C:/foo/test_foo.py") is True
    assert enforcer.is_test_file("C:/foo/foo_test.py") is True
    assert enforcer.is_test_file("C:/foo/conftest.py") is True
    assert enforcer.is_test_file("C:/foo/foo.spec.ts") is True
