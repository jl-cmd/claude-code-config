Audit jl-cmd/claude-code-config PR #397 for **Category K only** (codebase conflicts — incomplete propagation). Skip A–J. Sub-bucket forced-exhaustion mode: Category K is decomposed into 9 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: fix(hooks): improve hedging-language guardrail to surface user questions
Base SHA: 76f9c1a0048729b87c44626a3380dc840065c2fa (origin/main at PR open time)
Head SHA at audit time: 95ba07d6a8e0cd041e49ec9b93ea388dab00c2f3 (the commit Cursor Bugbot reviewed at PR #397 — the version BEFORE the fix in 8bcd5154 that this audit is meant to surface)
ID prefix: `find`.

This PR's first commit modified exactly one substring inside the hedging-language hook's block-response payload — replacing the closing instruction at lines 137-138 (inside the `block_response["reason"]` f-string) with new text directing the model to do additional research or prompt the user via `AskUserQuestion` with options + context. The wider file structure was left unchanged. The audit goal: identify any unchanged parallel site whose existing wording contradicts the new line 138 wording so they would interpolate into the same string and reach the model together.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**K1. Multi-site name renames**
- The diff at lines 137-138 introduces no rename — the symbol names `skill_reference`, `block_response`, `formatted_term_list`, `RESEARCH_MODE_SKILL_SEARCH_PATHS` are all unchanged.
- Verify by scanning the full file for any identifier that appears in the new line 138 wording but is also defined elsewhere.

**K2. Duplicated constants / defaults**
- The string token `"I don't know"` is the load-bearing duplicated literal across this PR. Search the file at SHA 95ba07d6 for every occurrence: line 126 (inside the `else` branch's `skill_reference` literal: `"...verify with sources or reply 'I don't know'"`) and the pre-diff line 138 (the OLD `"Either VERIFY it with a source or replace it with 'I don't know'."`).
- The diff updated occurrence #2 (line 138) but NOT occurrence #1 (line 126). Both occurrences exist in strings that interpolate into the SAME `block_response["reason"]` field — the model receives both texts.
- Verify whether the operator-facing primary instruction and the fallback instruction now disagree about whether `"I don't know"` is an allowed escape.

**K3. Primary path vs fallback path** ⭐ canonical K case
- The file's `if resolved_skill_path is not None:` branch (line 121) is the PRIMARY path; the `else:` branch (lines 123-127) is the FALLBACK (no-research-mode-skill-installed) path. Both produce values for the same variable `skill_reference`.
- Both paths' output flows into the SAME f-string at line 134 (`f"{skill_reference}\n\n"`), and from there into the SAME `block_response["reason"]` value sent to Claude.
- The diff at lines 137-138 updated the wording the *primary* path's downstream message ends with (closes the `"reply 'I don't know'"` escape; replaces with `"prompt the user via AskUserQuestion..."`). The fallback path's `skill_reference` text at lines 124-126 STILL contains `"verify with sources or reply 'I don't know'"` — unchanged from main.
- When the no-research-mode-skill fallback runs, the model receives: (a) the unchanged fallback text saying `"reply 'I don't know'"` is an option, AND (b) the new line 138 text saying `"AskUserQuestion"` is the path.
- Cite line 126 (unchanged-but-should-have-changed) and line 138 (changed) as the conflict pair. Describe the contradiction the model sees.

**K4. Feature flag / version gate consistency**
- No flags, no version gates in this file. The path-search list (`RESEARCH_MODE_SKILL_SEARCH_PATHS`) is environmental, not flag-gated.
- Verify by scanning the file for `if FLAG`, `if version`, environment-variable checks beyond `expanduser("~")`.

**K5. Producer-vs-consumer type contracts**
- `skill_reference` is typed as `str` in both branches (the primary uses `f"under the research-mode constraints..."`; the fallback uses a parenthesized string concatenation). Both interpolate cleanly into the line 134 f-string.
- `block_response` is `dict[str, Any]`-shaped; consumed by `json.dumps` on line 145. No producer/consumer type drift introduced by the diff.

**K6. Code vs documentation sync**
- Top-of-file docstring (lines 2-6) says: `"When detected, Claude is forced to re-check and respond with verified facts."`
- The new line 138 text explicitly extends this to a second branch — `"prompt the user via AskUserQuestion with some potential options + context if you are unable to find anything online"` — i.e., the hook is no longer just about verified facts; it now also legitimizes user-elicited disambiguation as a valid response.
- Verify whether the docstring still describes the post-diff behavior.

**K7. Code vs test sync**
- The test file at the same SHA contains an assertion: `assert "verify with sources or reply" in parsed_response["reason"]` (line 100 of the test file).
- This assertion was satisfied by the PRE-diff state because both line 126 (`"verify with sources or reply 'I don't know'"`) and line 138 (`"Either VERIFY it with a source or replace it with 'I don't know'"`) contained the substring `"verify with sources or reply"` — wait, only line 126 contains that exact substring. Verify whether the test passes at SHA 95ba07d6 against (a) line 126's untouched fallback text or (b) some other source.
- If the test passes solely because line 126 was NOT updated, then the test is a load-bearing witness to the K3 conflict — it asserts the very fallback text that the PR's intent (close the "I don't know" escape) was meant to remove.
- The merged version (SHA 8bcd5154) updates the test assertion to `"verify with sources or prompt the user via AskUserQuestion"`, which only matches if line 126 is ALSO updated to that wording. The K3 fix and the K7 fix landed together in the merge commit; at SHA 95ba07d6 the test still passes against the unchanged fallback.

**K8. Cross-file / cross-language contract sync**
- Single-language (Python) change; cross-language not applicable for this PR.
- Cross-file: the only other affected file is the test file (already covered by K7). No CSS / TS / JSON / config files touched.

**K9. Schema / data-shape propagation**
- `block_response` dict shape is unchanged; the same four keys (`decision`, `reason`, `systemMessage`, `suppressOutput`) are emitted as before. The hook protocol contract is preserved.
- Verify no schema drift in the JSON the hook prints to stdout.

## Cross-bucket questions to answer at the end

Q1: Is there a pattern in this diff where the primary site is updated but a parallel site (any sub-bucket) stays stale? Cite both lines.
Q2: What's the worst contradiction introduced by this PR — the one most likely to silently produce contradictory guardrail behavior at runtime when the no-research-mode-skill fallback fires? Cite `packages/claude-dev-env/hooks/blocking/hedging_language_blocker.py:<line>` for both the changed and unchanged sites.
Q3: Which existing test in `test_hedging_language_blocker.py` would have caught the K3 contradiction had it been calibrated to the post-diff intent, and which existing test instead passes "for the wrong reason" because the fallback was not updated alongside the primary?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket K1-K9, produce Shape A or Shape B (with ≥3 probes). Each Shape A finding must cite BOTH the diff line that was changed AND the parallel line that was missed — the conflict is between the two, not in either alone. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 parallel sites that should have been updated alongside the diff — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

## Diff (the buggy commit's change vs base)

```diff
@@ -134,7 +134,7 @@ def main() -> None:
             f"These words signal unverified claims. You MUST rewrite your response "
             f"{skill_reference}\n\n"
             f"Do NOT simply remove the hedging word and keep the unverified claim. "
-            f"Either VERIFY it with a source or replace it with 'I don't know'.\n\n"
+            f"Do more research to VERIFY it with a source, or prompt the user via AskUserQuestion with some potential options + context if you are unable to find anything online.\n\n"
             f"You MUST re-output the complete, revised response with the corrections applied."
         ),
```

(The rest of the PR at this SHA is a single test-file edit that does not bear on the hook's runtime behavior; the K conflict, if any, lives in the hook source file inlined below.)

## Full file at SHA 95ba07d6 (1 file, all lines in scope; the diff above only touches lines 137-138)

### packages/claude-dev-env/hooks/blocking/hedging_language_blocker.py
```python
#!/usr/bin/env python3
"""
Stop hook that blocks Claude responses containing hedging language.

Words like "likely", "probably", "presumably" signal unverified claims.
When detected, Claude is forced to re-check and respond with verified facts.
"""

import json
import os
import re
import sys
from pathlib import Path


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.messages import USER_FACING_NOTICE

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESEARCH_MODE_SKILL_SEARCH_PATHS = [
    os.path.join(PLUGIN_ROOT, "skills", "research-mode", "SKILL.md"),
    os.path.join(os.path.expanduser("~"), ".claude", "skills", "research-mode", "SKILL.md"),
    os.path.join(os.path.expanduser("~"), ".claude", "plugins", "marketplaces", "claude-deep-research", "skills", "research-mode", "SKILL.md"),
]

HEDGING_WORDS = [
    r"\blikely\b",
    r"\bunlikely\b",
    r"\bprobably\b",
    r"\bprobable\b",
    r"\bpresumably\b",
    r"\bperhaps\b",
    r"\bpossibly\b",
    r"\bseemingly\b",
    r"\bapparently\b",
    r"\barguably\b",
    r"\bsupposedly\b",
    r"\bostensibly\b",
    r"\bconceivably\b",
    r"\bplausibly\b",
]

HEDGING_PHRASES = [
    r"\bmight be\b",
    r"\bcould be\b",
    r"\bseems to be\b",
    r"\bappears to be\b",
    r"\bin all likelihood\b",
    r"\bmore likely than not\b",
    r"\bit.s possible that\b",
]

ALL_HEDGING_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in HEDGING_WORDS + HEDGING_PHRASES
]

CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE_CODE_PATTERN = re.compile(r"`[^`]+`")
QUOTED_BLOCK_PATTERN = re.compile(r"^>.*$", re.MULTILINE)


def strip_code_and_quotes(text: str) -> str:
    """Remove code blocks, inline code, and blockquotes to avoid false positives."""
    text = CODE_BLOCK_PATTERN.sub("", text)
    text = INLINE_CODE_PATTERN.sub("", text)
    text = QUOTED_BLOCK_PATTERN.sub("", text)
    return text


def find_hedging_words(text: str) -> list[str]:
    """Return all hedging words/phrases found in the text."""
    prose_text = strip_code_and_quotes(text)
    matched_terms = []

    for pattern in ALL_HEDGING_PATTERNS:
        all_matches = pattern.findall(prose_text)
        for each_match in all_matches:
            normalized_term = each_match.strip().lower()
            if normalized_term not in matched_terms:
                matched_terms.append(normalized_term)

    return matched_terms


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("stop_hook_active", False):
        sys.exit(0)

    assistant_message = hook_input.get("last_assistant_message", "")

    if not assistant_message:
        sys.exit(0)

    found_hedging_terms = find_hedging_words(assistant_message)

    if not found_hedging_terms:
        sys.exit(0)

    formatted_term_list = ", ".join(f'"{term}"' for term in found_hedging_terms)

    resolved_skill_path: str | None = None
    for each_skill_path in RESEARCH_MODE_SKILL_SEARCH_PATHS:
        if os.path.exists(each_skill_path):
            resolved_skill_path = each_skill_path
            break

    if resolved_skill_path is not None:
        skill_reference = f"under the research-mode constraints defined in:\n\n{resolved_skill_path}"
    else:
        skill_reference = (
            "under research-mode constraints "
            "(no research-mode skill installed; verify with sources or reply 'I don't know')"
        )

    block_response = {
        "decision": "block",
        "reason": (
            f"ANTI-HALLUCINATION GUARDRAIL: Your response contains hedging language: "
            f"{formatted_term_list}. "
            f"These words signal unverified claims. You MUST rewrite your response "
            f"{skill_reference}\n\n"
            f"Do NOT simply remove the hedging word and keep the unverified claim. "
            f"Do more research to VERIFY it with a source, or prompt the user via AskUserQuestion with some potential options + context if you are unable to find anything online.\n\n"
            f"You MUST re-output the complete, revised response with the corrections applied."
        ),
        "systemMessage": USER_FACING_NOTICE,
        "suppressOutput": True,
    }

    print(json.dumps(block_response))
    sys.exit(0)


if __name__ == "__main__":
    main()
```

### Companion test file at the same SHA (1 of 6 test cases inlined for K7 cross-reference)

```python
# packages/claude-dev-env/hooks/blocking/test_hedging_language_blocker.py
# Excerpt: the test that asserts the no-research-mode-skill fallback wording
def test_hedging_reason_contains_not_installed_notice_when_skill_absent():
    # ... fixture setup omitted ...
    assert parsed_response["decision"] == "block"
    assert "no research-mode skill installed" in parsed_response["reason"]
    assert "verify with sources or reply" in parsed_response["reason"]
    assert "SKILL.md" not in parsed_response["reason"]
    assert RESEARCH_MODE_SKILL_BODY_MARKER not in parsed_response["reason"]
```
