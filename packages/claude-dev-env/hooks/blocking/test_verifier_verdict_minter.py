"""Behavioral tests for verifier_verdict_minter against real git repos."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_verification_verdict_store import (    BEHAVIORAL_MODULE,
    build_cloned_repo,
    isolated_home,
)
from verification_verdict_store import (    branch_surface_manifest,
    load_valid_verdict,
    manifest_sha256,
    resolve_merge_base,
    resolve_repo_root,
)
from verifier_verdict_minter import (    assistant_text_blocks,
    last_verdict_in_blocks,
    mint_for_payload,
)

_ = isolated_home

CLEAN_VERDICT_TEXT = 'All layers clean.\n\n```verdict\n{"all_pass": true, "findings": []}\n```\n'


def write_transcript(tmp_path: Path, assistant_texts: list[str]) -> Path:
    transcript_file = tmp_path / "transcript.jsonl"
    transcript_lines = []
    for each_text in assistant_texts:
        transcript_lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": each_text}]},
                }
            )
        )
    transcript_lines.append("not json at all")
    transcript_file.write_text("\n".join(transcript_lines), encoding="utf-8")
    return transcript_file


class TestTranscriptParsing:
    def test_should_collect_assistant_texts_and_skip_noise(self, tmp_path: Path) -> None:
        transcript_file = write_transcript(tmp_path, ["first", CLEAN_VERDICT_TEXT])
        assert assistant_text_blocks(str(transcript_file)) == [
            "first",
            CLEAN_VERDICT_TEXT,
        ]

    def test_should_take_last_wellformed_verdict(self) -> None:
        stale_fence = '```verdict\n{"all_pass": false, "findings": [{"check": "tests", "detail": "boom"}]}\n```'
        malformed_fence = "```verdict\nnot json\n```"
        verdict = last_verdict_in_blocks([stale_fence, CLEAN_VERDICT_TEXT, malformed_fence])
        assert verdict == {"all_pass": True, "findings": []}

    def test_should_reject_fences_missing_contract_keys(self) -> None:
        keyless_fence = '```verdict\n{"all_pass": "yes"}\n```'
        assert last_verdict_in_blocks([keyless_fence]) is None
        assert last_verdict_in_blocks(["no fence here"]) is None


class TestMinting:
    def test_should_mint_verdict_bound_to_live_diff(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        changed = BEHAVIORAL_MODULE.replace("left + right", "left - right")
        (clone_dir / "module.py").write_text(changed, encoding="utf-8")
        transcript_file = write_transcript(tmp_path, [CLEAN_VERDICT_TEXT])
        minted_path = mint_for_payload(
            {
                "agent_type": "fable-verifier",
                "agent_id": "agent-77",
                "agent_transcript_path": str(transcript_file),
                "cwd": str(clone_dir),
            }
        )
        assert minted_path is not None
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        live_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        minted_verdict = load_valid_verdict(repo_root, live_hash)
        assert minted_verdict is not None
        assert minted_verdict["minted_from_agent_id"] == "agent-77"

    def test_should_ignore_other_agent_types(self, tmp_path: Path, isolated_home: Path) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        transcript_file = write_transcript(tmp_path, [CLEAN_VERDICT_TEXT])
        assert (
            mint_for_payload(
                {
                    "agent_type": "clean-coder",
                    "agent_transcript_path": str(transcript_file),
                    "cwd": str(clone_dir),
                }
            )
            is None
        )

    def test_should_mint_nothing_from_parent_transcript_key(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        parent_transcript_file = write_transcript(tmp_path, [CLEAN_VERDICT_TEXT])
        assert (
            mint_for_payload(
                {
                    "agent_type": "fable-verifier",
                    "transcript_path": str(parent_transcript_file),
                    "cwd": str(clone_dir),
                }
            )
            is None
        )

    def test_should_mint_nothing_without_a_verdict_fence(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        transcript_file = write_transcript(tmp_path, ["I checked things. Looks fine."])
        assert (
            mint_for_payload(
                {
                    "agent_type": "fable-verifier",
                    "agent_transcript_path": str(transcript_file),
                    "cwd": str(clone_dir),
                }
            )
            is None
        )

    def test_should_record_failing_verdict_that_gate_rejects(
        self, tmp_path: Path, isolated_home: Path
    ) -> None:
        clone_dir = build_cloned_repo(tmp_path)
        changed = BEHAVIORAL_MODULE.replace("left + right", "left - right")
        (clone_dir / "module.py").write_text(changed, encoding="utf-8")
        failing_text = '```verdict\n{"all_pass": false, "findings": [{"check": "pytest", "detail": "1 new failure"}]}\n```'
        transcript_file = write_transcript(tmp_path, [failing_text])
        minted_path = mint_for_payload(
            {
                "agent_type": "fable-verifier",
                "agent_id": "agent-78",
                "agent_transcript_path": str(transcript_file),
                "cwd": str(clone_dir),
            }
        )
        assert minted_path is not None
        repo_root = resolve_repo_root(str(clone_dir))
        merge_base = resolve_merge_base(repo_root)
        live_hash = manifest_sha256(branch_surface_manifest(repo_root, merge_base))
        assert load_valid_verdict(repo_root, live_hash) is None
