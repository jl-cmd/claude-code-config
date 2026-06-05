"""Behavior tests for publish.py helpers.

These tests cover the pure helpers that do not require Drive API or OAuth:
recipient merging, HTML detection, and token-path resolution. Tests follow
the project's no-mocks rule and exercise the production code paths directly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_script_dir = str(Path(__file__).resolve().parent)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

import publish
from config.secure_share_constants import (
    ALL_DEFAULT_VIEWER_EMAILS,
    CLAUDE_PLUGIN_DATA_ENV_NAME,
    TOKEN_PATH_HOME_RELATIVE,
    TOKEN_PATH_PLUGIN_DATA_RELATIVE,
)

DEFAULT_RECIPIENT = "melclombardi@gmail.com"


def should_always_include_default_recipient_when_no_extras_given():
    merged = publish._merge_recipients([])
    assert merged == ALL_DEFAULT_VIEWER_EMAILS
    assert DEFAULT_RECIPIENT in merged


def should_append_extra_recipients_after_default():
    merged = publish._merge_recipients(["alice@example.com", "bob@example.com"])
    assert merged[0] == DEFAULT_RECIPIENT
    assert "alice@example.com" in merged
    assert "bob@example.com" in merged
    assert len(merged) == 3


def should_dedupe_default_recipient_passed_again():
    merged = publish._merge_recipients([DEFAULT_RECIPIENT])
    assert merged == [DEFAULT_RECIPIENT]


def should_dedupe_repeated_extras():
    merged = publish._merge_recipients(["x@example.com", "x@example.com"])
    assert merged == [DEFAULT_RECIPIENT, "x@example.com"]


def should_skip_empty_strings_in_extras():
    merged = publish._merge_recipients(["", "alice@example.com", ""])
    assert merged == [DEFAULT_RECIPIENT, "alice@example.com"]


def should_detect_html_input_by_extension():
    assert publish._is_html_input(Path("report.html")) is True
    assert publish._is_html_input(Path("report.htm")) is True


def should_detect_html_input_case_insensitively():
    assert publish._is_html_input(Path("REPORT.HTML")) is True
    assert publish._is_html_input(Path("Report.Htm")) is True


def should_not_treat_pdf_or_md_as_html():
    assert publish._is_html_input(Path("report.pdf")) is False
    assert publish._is_html_input(Path("report.md")) is False
    assert publish._is_html_input(Path("report.txt")) is False


def should_resolve_token_path_under_home_when_env_unset(monkeypatch):
    monkeypatch.delenv(CLAUDE_PLUGIN_DATA_ENV_NAME, raising=False)
    resolved = publish._resolve_token_path()
    assert resolved == Path.home() / TOKEN_PATH_HOME_RELATIVE


def should_resolve_token_path_under_plugin_data_when_env_set(monkeypatch, tmp_path):
    monkeypatch.setenv(CLAUDE_PLUGIN_DATA_ENV_NAME, str(tmp_path))
    resolved = publish._resolve_token_path()
    assert resolved == tmp_path / TOKEN_PATH_PLUGIN_DATA_RELATIVE


def should_resolve_token_path_under_home_when_env_is_empty_string(monkeypatch):
    monkeypatch.setenv(CLAUDE_PLUGIN_DATA_ENV_NAME, "")
    resolved = publish._resolve_token_path()
    assert resolved == Path.home() / TOKEN_PATH_HOME_RELATIVE


def should_parse_argv_into_namespace_with_input_email_and_title(tmp_path):
    fake_source = tmp_path / "report.pdf"
    fake_source.write_bytes(b"%PDF-1.4")
    parsed = publish._parse_arguments(
        [
            "--input",
            str(fake_source),
            "--email",
            "alice@example.com",
            "--email",
            "bob@example.com",
            "--title",
            "Quarterly Report",
        ]
    )
    assert parsed.input == fake_source
    assert parsed.email == ["alice@example.com", "bob@example.com"]
    assert parsed.title == "Quarterly Report"


def should_parse_argv_with_no_emails_or_title():
    parsed = publish._parse_arguments(["--input", "some_file.pdf"])
    assert parsed.input == Path("some_file.pdf")
    assert parsed.email == []
    assert parsed.title is None
