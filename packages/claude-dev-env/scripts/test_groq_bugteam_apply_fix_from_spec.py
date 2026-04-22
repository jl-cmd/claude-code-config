"""Tests for groq_bugteam.apply_fix_from_spec().

Covers the Claude-authored fix-spec pipeline: replacement_code splicing,
intended_change derivation, acceptance-criterion self-check, out-of-range
guard, and trailing-newline preservation. All Groq HTTP calls are
monkeypatched; no network activity.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest


def _load_groq_bugteam_module():
    scripts_directory = pathlib.Path(__file__).parent
    sys.path.insert(0, str(scripts_directory))
    modules_to_remove = [
        each_module_name
        for each_module_name in list(sys.modules)
        if each_module_name == "groq_bugteam"
        or each_module_name.startswith("groq_bugteam.")
    ]
    for each_module_name in modules_to_remove:
        del sys.modules[each_module_name]
    module_path = scripts_directory / "groq_bugteam.py"
    module_spec = importlib.util.spec_from_file_location("groq_bugteam", module_path)
    loaded_module = importlib.util.module_from_spec(module_spec)
    sys.modules["groq_bugteam"] = loaded_module
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


groq_bugteam = _load_groq_bugteam_module()


FAKE_API_KEY = "gsk_test_placeholder_value"


def _stub_groq_response(monkeypatch, response_object: dict) -> None:
    """Force call_groq_with_fallback() to return a synthetic JSON payload."""

    def fake_call(api_key, messages, temperature, max_completion_tokens):
        return groq_bugteam.GroqCallResult(
            content=json.dumps(response_object),
            model="fake-model",
        )

    monkeypatch.setenv("GROQ_API_KEY", FAKE_API_KEY)
    monkeypatch.setattr(groq_bugteam, "call_groq_with_fallback", fake_call)


class TestApplyFixFromSpecReplacementCode:
    def test_applies_replacement_code_byte_for_byte_outside_edit(self, monkeypatch):
        original_file = "line_one\nline_two\nline_three\n"
        spec_list = [
            {
                "finding_index": 0,
                "severity": "P1",
                "category": "J",
                "file": "sample.py",
                "target_line_start": 2,
                "target_line_end": 2,
                "intended_change": "replace line_two",
                "replacement_code": "line_two_fixed",
                "acceptance_criteria": ["line_two_fixed appears on line 2"],
            }
        ]
        patched_file = "line_one\nline_two_fixed\nline_three\n"
        fake_response = {
            "updated_content": patched_file,
            "applied_finding_indexes": [0],
            "skipped": [],
            "acceptance_checks": [
                {
                    "finding_index": 0,
                    "criterion": "line_two_fixed appears on line 2",
                    "met": True,
                }
            ],
        }
        _stub_groq_response(monkeypatch, fake_response)

        outcome = groq_bugteam.apply_fix_from_spec(spec_list, original_file)

        assert outcome["updated_content"] == patched_file
        assert outcome["applied_finding_indexes"] == [0]
        assert outcome["skipped"] == []


class TestApplyFixFromSpecDerivedEdit:
    def test_derives_minimal_edit_when_replacement_absent(self, monkeypatch):
        original_file = "value = 1\nreturn value\n"
        spec_list = [
            {
                "finding_index": 3,
                "severity": "P2",
                "category": "E",
                "file": "sample.py",
                "target_line_start": 1,
                "target_line_end": 1,
                "intended_change": "rename value to total_count",
                "acceptance_criteria": [
                    "variable named total_count exists on line 1",
                    "the literal token value does not appear on line 1",
                ],
            }
        ]
        patched_file = "total_count = 1\nreturn value\n"
        fake_response = {
            "updated_content": patched_file,
            "applied_finding_indexes": [3],
            "skipped": [],
            "acceptance_checks": [
                {
                    "finding_index": 3,
                    "criterion": "variable named total_count exists on line 1",
                    "met": True,
                },
                {
                    "finding_index": 3,
                    "criterion": "the literal token value does not appear on line 1",
                    "met": True,
                },
            ],
        }
        _stub_groq_response(monkeypatch, fake_response)

        outcome = groq_bugteam.apply_fix_from_spec(spec_list, original_file)

        assert outcome["updated_content"] == patched_file
        assert outcome["applied_finding_indexes"] == [3]


class TestApplyFixFromSpecAcceptanceFailure:
    def test_moves_finding_to_skipped_when_any_criterion_unmet(self, monkeypatch):
        original_file = "alpha\nbeta\n"
        spec_list = [
            {
                "finding_index": 7,
                "severity": "P1",
                "category": "H",
                "file": "sample.py",
                "target_line_start": 2,
                "target_line_end": 2,
                "intended_change": "replace beta with gamma",
                "replacement_code": "gamma",
                "acceptance_criteria": [
                    "gamma appears on line 2",
                    "delta appears on line 2",
                ],
            }
        ]
        patched_file = "alpha\ngamma\n"
        fake_response = {
            "updated_content": patched_file,
            "applied_finding_indexes": [7],
            "skipped": [],
            "acceptance_checks": [
                {
                    "finding_index": 7,
                    "criterion": "gamma appears on line 2",
                    "met": True,
                },
                {
                    "finding_index": 7,
                    "criterion": "delta appears on line 2",
                    "met": False,
                },
            ],
        }
        _stub_groq_response(monkeypatch, fake_response)

        outcome = groq_bugteam.apply_fix_from_spec(spec_list, original_file)

        assert 7 not in outcome["applied_finding_indexes"]
        skipped_indexes = [each["finding_index"] for each in outcome["skipped"]]
        assert 7 in skipped_indexes
        reason_text = next(
            each["reason"] for each in outcome["skipped"] if each["finding_index"] == 7
        )
        assert "delta appears on line 2" in reason_text


class TestApplyFixFromSpecOutOfRange:
    def test_skips_when_target_lines_out_of_range(self, monkeypatch):
        original_file = "only_line\n"
        spec_list = [
            {
                "finding_index": 2,
                "severity": "P2",
                "category": "E",
                "file": "sample.py",
                "target_line_start": 50,
                "target_line_end": 51,
                "intended_change": "fix beyond file end",
                "replacement_code": "noop",
                "acceptance_criteria": ["noop replaces line 50"],
            }
        ]
        fake_response = {
            "updated_content": original_file,
            "applied_finding_indexes": [],
            "skipped": [
                {
                    "finding_index": 2,
                    "reason": "target_line_start out of range",
                }
            ],
            "acceptance_checks": [],
        }
        _stub_groq_response(monkeypatch, fake_response)

        outcome = groq_bugteam.apply_fix_from_spec(spec_list, original_file)

        assert outcome["updated_content"] == original_file
        assert outcome["applied_finding_indexes"] == []
        assert outcome["skipped"][0]["finding_index"] == 2


class TestApplyFixFromSpecTrailingNewline:
    def test_preserves_trailing_newline_when_original_had_one(self, monkeypatch):
        original_file = "alpha\nbeta\n"
        spec_list = [
            {
                "finding_index": 0,
                "severity": "P1",
                "category": "J",
                "file": "sample.py",
                "target_line_start": 1,
                "target_line_end": 1,
                "intended_change": "rename alpha to alpha_fixed",
                "replacement_code": "alpha_fixed",
                "acceptance_criteria": ["alpha_fixed appears on line 1"],
            }
        ]
        fake_response = {
            "updated_content": "alpha_fixed\nbeta",
            "applied_finding_indexes": [0],
            "skipped": [],
            "acceptance_checks": [
                {
                    "finding_index": 0,
                    "criterion": "alpha_fixed appears on line 1",
                    "met": True,
                }
            ],
        }
        _stub_groq_response(monkeypatch, fake_response)

        outcome = groq_bugteam.apply_fix_from_spec(spec_list, original_file)

        assert outcome["updated_content"].endswith("\n")

    def test_preserves_absence_of_trailing_newline(self, monkeypatch):
        original_file = "alpha\nbeta"
        spec_list = [
            {
                "finding_index": 0,
                "severity": "P1",
                "category": "J",
                "file": "sample.py",
                "target_line_start": 1,
                "target_line_end": 1,
                "intended_change": "rename alpha to alpha_fixed",
                "replacement_code": "alpha_fixed",
                "acceptance_criteria": ["alpha_fixed appears on line 1"],
            }
        ]
        fake_response = {
            "updated_content": "alpha_fixed\nbeta\n",
            "applied_finding_indexes": [0],
            "skipped": [],
            "acceptance_checks": [
                {
                    "finding_index": 0,
                    "criterion": "alpha_fixed appears on line 1",
                    "met": True,
                }
            ],
        }
        _stub_groq_response(monkeypatch, fake_response)

        outcome = groq_bugteam.apply_fix_from_spec(spec_list, original_file)

        assert not outcome["updated_content"].endswith("\n")
