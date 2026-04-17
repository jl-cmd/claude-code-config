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
    negative = -1
    return count + increment + negative
'''

ALLOWED_NEGATIVE_ONE_IN_BINARY_EXPRESSION = '''
def process(total):
    return total * -1
'''

ALLOWED_NEGATIVE_ONE_IN_RETURN = '''
def process():
    return -1
'''

BAD_NEGATIVE_LITERAL_TWO = '''
def process():
    return total * -2
'''

ALLOWED_EMPTY_STRING = '''
def process():
    result = ""
    return result
'''

BAD_LITERAL_TWO = '''
def process():
    doubled = something * 2
    return doubled
'''

BAD_LITERAL_ONE_HUNDRED = '''
def process():
    percentage = fraction * 100
    return percentage
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

    def test_negative_one_allowed_in_binary_expression(self) -> None:
        tree = ast.parse(ALLOWED_NEGATIVE_ONE_IN_BINARY_EXPRESSION)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_negative_one_allowed_in_return_expression(self) -> None:
        tree = ast.parse(ALLOWED_NEGATIVE_ONE_IN_RETURN)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_negative_literal_two_is_flagged_with_signed_value(self) -> None:
        tree = ast.parse(BAD_NEGATIVE_LITERAL_TWO)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "-2" in violations[0].message

    def test_empty_string_allowed(self) -> None:
        tree = ast.parse(ALLOWED_EMPTY_STRING)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_check_magic_values_should_flag_literal_two_in_function_body(self) -> None:
        tree = ast.parse(BAD_LITERAL_TWO)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "2" in violations[0].message

    def test_check_magic_values_should_flag_literal_one_hundred_in_function_body(self) -> None:
        tree = ast.parse(BAD_LITERAL_ONE_HUNDRED)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "100" in violations[0].message
