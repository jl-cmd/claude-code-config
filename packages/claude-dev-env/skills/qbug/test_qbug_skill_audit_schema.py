"""Tests verifying qbug SKILL.md contains required audit schema structural elements.

Checks the structured proof-of-absence requirement, adversarial pass directive,
Haiku secondary auditor spawn, JSON persistence, and de-dup merge logic.
"""

from __future__ import annotations

from pathlib import Path


SKILL_FILE_PATH = Path(__file__).parent / "SKILL.md"
PROMPTS_FILE_PATH = Path(__file__).parent.parent / "bugteam" / "PROMPTS.md"


def _load_skill_text() -> str:
    return SKILL_FILE_PATH.read_text(encoding="utf-8")


def _load_prompts_text() -> str:
    return PROMPTS_FILE_PATH.read_text(encoding="utf-8")


def test_should_require_structured_finding_schema_in_audit_step() -> None:
    skill_text = _load_skill_text()
    assert "evidence_files" in skill_text, (
        "AUDIT step must require structured finding with evidence_files[]"
    )
    assert "proof_of_absence" in skill_text, (
        "AUDIT step must require structured proof-of-absence for clean categories"
    )


def test_should_reject_bare_verified_clean_labels() -> None:
    skill_text = _load_skill_text()
    assert "lines_quoted" in skill_text, (
        "Proof-of-absence must require lines_quoted[] not bare 'verified clean'"
    )
    assert "adversarial_probes" in skill_text, (
        "Proof-of-absence must require adversarial_probes[]"
    )


def test_should_require_adversarial_second_pass_in_audit_step() -> None:
    skill_text = _load_skill_text()
    assert "Assume your first pass missed" in skill_text, (
        "AUDIT step must include adversarial second-pass re-prompt"
    )


def test_should_require_haiku_secondary_auditor_spawn() -> None:
    skill_text = _load_skill_text()
    assert "haiku" in skill_text.lower(), (
        "SKILL.md must reference Haiku secondary auditor"
    )
    assert "secondary" in skill_text.lower(), (
        "SKILL.md must reference secondary auditor concept"
    )


def test_should_require_dedup_merge_by_file_line_category() -> None:
    skill_text = _load_skill_text()
    assert (
        "file, line, category" in skill_text or "(file, line, category)" in skill_text
    ), "De-dup key must be (file, line, category)"


def test_should_require_severity_max_wins_on_conflict() -> None:
    skill_text = _load_skill_text()
    assert (
        "max wins" in skill_text.lower() or "severity conflict" in skill_text.lower()
    ), "Severity conflict resolution must specify max wins"


def test_should_require_loop_n_audit_json_persistence() -> None:
    skill_text = _load_skill_text()
    assert "loop-" in skill_text and "audit.json" in skill_text, (
        "SKILL.md must reference loop-N-audit.json persistence path"
    )


def test_should_require_findings_and_proof_of_absence_keys_in_json() -> None:
    skill_text = _load_skill_text()
    assert '"findings"' in skill_text or "findings[]" in skill_text, (
        "loop-N-audit.json must have findings[] key"
    )
    assert '"proof_of_absence"' in skill_text or "proof_of_absence[]" in skill_text, (
        "loop-N-audit.json must have proof_of_absence[] key"
    )


def test_should_require_files_opened_in_proof_of_absence() -> None:
    skill_text = _load_skill_text()
    assert "files_opened" in skill_text, (
        "Proof-of-absence struct must include files_opened[]"
    )


def test_prompts_md_should_contain_expanded_category_e_dead_code_variants() -> None:
    prompts_text = _load_prompts_text()
    assert (
        "dead parameter" in prompts_text.lower()
        or "dead parameters" in prompts_text.lower()
    ), "Category E must cover dead parameters"
    assert (
        "dead local" in prompts_text.lower() or "dead locals" in prompts_text.lower()
    ), "Category E must cover dead locals"
    assert (
        "dead import" in prompts_text.lower() or "dead imports" in prompts_text.lower()
    ), "Category E must cover dead imports"
    assert (
        "dead branch" in prompts_text.lower() or "dead branches" in prompts_text.lower()
    ), "Category E must cover dead branches"
    assert (
        "dead return" in prompts_text.lower() or "dead returns" in prompts_text.lower()
    ), "Category E must cover dead returns"
