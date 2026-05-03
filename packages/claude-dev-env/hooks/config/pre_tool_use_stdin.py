"""Shared stdin parsing for PreToolUse hooks that expect one JSON object."""

from __future__ import annotations

import json
import sys


def _read_stdin_text() -> str | None:
    try:
        raw_bytes = sys.stdin.buffer.read()
    except (AttributeError, OSError):
        try:
            decoded_text = sys.stdin.read()
        except OSError:
            return None
        if decoded_text is None:
            return None
        return decoded_text
    return raw_bytes.decode("utf-8", errors="replace")


def read_hook_input_dictionary_from_stdin() -> dict[str, object] | None:
    """Return the hook payload dict, or None when stdin is empty or not a JSON object.

    Reads the full stdin stream, strips a UTF-8 BOM and surrounding whitespace, then
    parses JSON. Malformed JSON, non-object roots, and empty payloads yield None so
    callers can exit zero without treating the hook as a hard failure.
    """
    decoded_text = _read_stdin_text()
    if decoded_text is None:
        return None
    normalized_text = decoded_text.strip().removeprefix("\ufeff").strip()
    if not normalized_text:
        return None
    try:
        parsed_payload = json.loads(normalized_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_payload, dict):
        return None
    return parsed_payload
