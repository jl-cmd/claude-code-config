"""Tests for magic value detection."""

import ast

import pytest

from magic_value_checks import (
    check_magic_values,
)
from validator_base import Violation


GOOD_NAMED_CONSTANTS = '''
API_TIMEOUT_MS = 5000
HASH_DELIMITER = "__"

def process():
    timeout = API_TIMEOUT_MS
    return f"key{HASH_DELIMITER}value"
'''

BAD_MAGIC_NUMBER = '''
def process():
    timeout = 5000
    return timeout
'''

ALLOWED_SMALL_NUMBERS = '''
def process():
    count = 0
    increment = 1
    doubled = count * 2
    return count + 1
'''

ALLOWED_EMPTY_STRING = '''
def process():
    result = ""
    return result
'''

DICT_VALUED_CONSTANT = '''
SETTINGS = {"timeout": 30, "retries": 5}
'''

TUPLE_VALUED_CONSTANT = '''
RETRY_DELAYS = (2, 4, 8)
'''

LIST_VALUED_CONSTANT = '''
PORTS = [8080, 8443, 9000]
'''

NESTED_DICT_VALUED_CONSTANT = '''
CONFIG = {"db": {"port": 5432}}
'''

NON_CONSTANT_ASSIGNMENT_IN_FUNCTION = '''
def configure():
    delay = 30
    return delay
'''

SCALAR_MAGIC_NUMBER_OUTSIDE_CONSTANT = '''
def compute():
    return 30 + 5000
'''


class TestMagicValues:
    def test_named_constants_pass(self) -> None:
        tree = ast.parse(GOOD_NAMED_CONSTANTS)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_magic_number_fails(self) -> None:
        tree = ast.parse(BAD_MAGIC_NUMBER)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "5000" in violations[0].message

    def test_small_numbers_allowed(self) -> None:
        tree = ast.parse(ALLOWED_SMALL_NUMBERS)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_empty_string_allowed(self) -> None:
        tree = ast.parse(ALLOWED_EMPTY_STRING)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_exempt_numbers_inside_dict_valued_constant(self) -> None:
        tree = ast.parse(DICT_VALUED_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_exempt_numbers_inside_tuple_valued_constant(self) -> None:
        tree = ast.parse(TUPLE_VALUED_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_exempt_numbers_inside_list_valued_constant(self) -> None:
        tree = ast.parse(LIST_VALUED_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_exempt_numbers_inside_nested_dict_valued_constant(self) -> None:
        tree = ast.parse(NESTED_DICT_VALUED_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_still_flag_numbers_in_function_body_assignments(self) -> None:
        tree = ast.parse(NON_CONSTANT_ASSIGNMENT_IN_FUNCTION)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "30" in violations[0].message

    def test_should_still_flag_scalar_magic_number_outside_constant(self) -> None:
        tree = ast.parse(SCALAR_MAGIC_NUMBER_OUTSIDE_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        flagged_numbers = {violation.message for violation in violations}
        assert any("30" in message for message in flagged_numbers)
        assert any("5000" in message for message in flagged_numbers)
