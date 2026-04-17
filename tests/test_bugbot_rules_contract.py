"""Specifications that .cursor/BUGBOT.md matches hook-enforced CODE_RULES exemptions."""

from pathlib import Path


def _bugbot_text() -> str:
    repository_root = Path(__file__).resolve().parent.parent
    bugbot_path = repository_root / ".cursor" / "BUGBOT.md"
    return bugbot_path.read_text(encoding="utf-8")


def test_bugbot_documents_upper_snake_exemptions_matching_hook() -> None:
    """code-rules-enforcer exempts migrations, workflow registries, and tests."""
    text = _bugbot_text()
    assert "/migrations/" in text
    assert "_tab.py" in text
    assert "states.py" in text
    assert "modules.py" in text
    assert "/workflow/" in text
    assert "conftest" in text
    assert "/tests/" in text


def test_bugbot_file_length_matches_hook_advisory_behavior() -> None:
    """Hook uses stderr advisories at 400 and 1000 lines; it does not block on length."""
    text = _bugbot_text()
    lower = text.lower()
    assert "400" in text
    assert "1000" in text
    assert "advisory" in lower
    assert "stderr" in lower
    assert "hard limit" not in lower
