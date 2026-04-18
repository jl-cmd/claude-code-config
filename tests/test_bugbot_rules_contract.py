"""Specifications that LLM review docs match hook-enforced CODE_RULES exemptions."""

from pathlib import Path


def _repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _bugbot_text() -> str:
    bugbot_path = _repository_root() / ".cursor" / "BUGBOT.md"
    return bugbot_path.read_text(encoding="utf-8")


def _copilot_instructions_text() -> str:
    copilot_path = _repository_root() / ".github" / "copilot-instructions.md"
    return copilot_path.read_text(encoding="utf-8")


def test_bugbot_documents_upper_snake_exemptions_matching_hook() -> None:
    """code-rules-enforcer exempts migrations, workflow registries, and tests."""
    text = _bugbot_text()
    assert "/migrations/" in text
    assert "_tab.py" in text
    assert "/states.py" in text
    assert "/modules.py" in text
    assert "/workflow/" in text
    assert "conftest" in text
    assert "/tests/" in text


def test_bugbot_workflow_registry_phrasing_describes_substring_match() -> None:
    """BUGBOT phrasing must describe substring matching (hook behavior), not basename-only matching."""
    text = _bugbot_text()
    assert "contains the substring" in text
    workflow_bullet_start = text.find("Workflow registries:")
    assert workflow_bullet_start != -1
    newline_after_bullet = text.find("\n", workflow_bullet_start)
    workflow_bullet = text[workflow_bullet_start:newline_after_bullet]
    assert "contains the substring" in workflow_bullet
    assert "/workflow/" in workflow_bullet
    assert "/states.py" in workflow_bullet
    assert "/modules.py" in workflow_bullet
    assert "_tab.py" in workflow_bullet
    assert "basename" not in workflow_bullet.lower()


def test_bugbot_file_length_matches_hook_advisory_behavior() -> None:
    """Hook uses stderr advisories at 400 and 1000 lines; it does not block on length."""
    text = _bugbot_text()
    lower = text.lower()
    assert "400" in text
    assert "1000" in text
    assert "advisory" in lower
    assert "stderr" in lower
    assert "hard limit" not in lower


def test_copilot_instructions_upper_snake_exemptions_match_hook() -> None:
    """GitHub Copilot instructions stay aligned with code-rules-enforcer carve-outs."""
    text = _copilot_instructions_text()
    assert "/migrations/" in text
    assert "/workflow/" in text
    assert "_tab.py" in text
    assert "/states.py" in text
    assert "/modules.py" in text
    assert "test_" in text
    assert "conftest" in text
    assert "/tests/" in text


def test_copilot_instructions_file_length_matches_hook_advisory_behavior() -> None:
    """Hook uses stderr advisories at 400 and 1000 lines; it does not block on length."""
    text = _copilot_instructions_text()
    lower = text.lower()
    assert "400" in text
    assert "1000" in text
    assert "advisory" in lower
    assert "stderr" in lower
    assert "hard limit" not in lower


def test_copilot_workflow_registry_phrasing_describes_substring_match() -> None:
    """Workflow exemption must match WORKFLOW_REGISTRY_PATTERNS (path substrings, not basename-only)."""
    text = _copilot_instructions_text()
    workflow_label = "Workflow registries:"
    workflow_bullet_start = text.index(workflow_label)
    newline_after_bullet = text.index("\n", workflow_bullet_start)
    workflow_bullet = text[workflow_bullet_start:newline_after_bullet]
    lower_bullet = workflow_bullet.lower()
    assert "substring" in lower_bullet
    assert "/workflow/" in workflow_bullet
    assert "/states.py" in workflow_bullet
    assert "/modules.py" in workflow_bullet
    assert "_tab.py" in workflow_bullet
    assert "basename" not in lower_bullet
