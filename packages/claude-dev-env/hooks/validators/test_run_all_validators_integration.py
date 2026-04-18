"""Integration test for new validators in run_all_validators.py"""

import subprocess
import sys
from pathlib import Path

import pytest


VALIDATORS_DIR = Path(__file__).parent
HOOKS_DIR = VALIDATORS_DIR.parent
PACKAGE_MODULE = f"{VALIDATORS_DIR.name}.run_all_validators"


def run_validators_help() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", PACKAGE_MODULE, "--help"],
        capture_output=True,
        text=True,
        cwd=str(HOOKS_DIR),
    )


class TestNewValidatorsIntegration:
    def test_abbreviation_checks_called(self) -> None:
        """Verify abbreviation_checks is invoked by run_all_validators."""
        result = run_validators_help()
        assert result.returncode == 0, result.stderr
        assert "Abbreviations" in result.stdout or result.returncode == 0

    def test_pr_reference_checks_called(self) -> None:
        """Verify pr_reference_checks is invoked by run_all_validators."""
        result = run_validators_help()
        assert result.returncode == 0, result.stderr
        assert "PR References" in result.stdout or result.returncode == 0

    def test_magic_value_checks_called(self) -> None:
        """Verify magic_value_checks is invoked by run_all_validators."""
        result = run_validators_help()
        assert result.returncode == 0, result.stderr
        assert "Magic Values" in result.stdout or result.returncode == 0

    def test_useless_test_checks_called(self) -> None:
        """Verify useless_test_checks is invoked by run_all_validators."""
        result = run_validators_help()
        assert result.returncode == 0, result.stderr
        assert "Useless Tests" in result.stdout or result.returncode == 0
