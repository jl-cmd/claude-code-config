import json
import re
import sys
from pathlib import Path

from config.constants import (
    ALL_ASSISTANT_USER_TYPES,
    ALL_OUTCOME_MARKERS,
    ALL_SHALLOW_PATTERNS,
    GAP_EVIDENCE_THRESHOLD,
    HEADER_WIDTH,
    MAXIMUM_PR_NUMBER,
    MAXIMUM_REPORT_COUNT,
    MINIMUM_PR_NUMBER,
)


def extract_text(all_entry_data: dict) -> str:
    entry_type = all_entry_data.get("type", "")
    if entry_type == "system":
        return all_entry_data.get("content", "") or ""
    if entry_type == "queue-operation":
        return all_entry_data.get("content", "") or ""
    if entry_type in ALL_ASSISTANT_USER_TYPES:
        message = all_entry_data.get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for each_content_item in content:
                if isinstance(each_content_item, dict) and each_content_item.get("type") == "text":
                    text_parts.append(each_content_item.get("text", ""))
            return "\n".join(text_parts)
    return ""


def extract_session(path: str) -> dict:
    outcome_markers = ALL_OUTCOME_MARKERS
    extracted = {
        "path": path,
        "name": Path(path).stem,
        "pr_numbers": [],
        "repo": None,
        "loops": [],
        "bugbot_retriggers": 0,
        "outcome": None,
        "has_bugteam": False,
        "has_pr_converge": False,
    }
    with open(path, "r", encoding="utf-8", errors="replace") as file_handle:
        for each_line in file_handle:
            each_line = each_line.strip()
            if not each_line:
                continue
            try:
                parsed_entry = json.loads(each_line)
            except json.JSONDecodeError:
                continue
            text = extract_text(parsed_entry)
            for each_match in re.finditer(r"[Pp][Rr]\s*#?(\d+)", text):
                pr = int(each_match.group(1))
                if MINIMUM_PR_NUMBER <= pr <= MAXIMUM_PR_NUMBER and pr not in extracted["pr_numbers"]:
                    extracted["pr_numbers"].append(pr)
            if not extracted["repo"]:
                repo_match = re.search(r"(jl-cmd|JonEcho)/[a-z0-9_-]+", text)
                if repo_match:
                    extracted["repo"] = repo_match.group()
            loop_match = re.search(r"(?:bugteam\s+)?loop\s+(\d+)", text, re.I)
            if loop_match:
                loop_number = int(loop_match.group(1))
                if not any(each_loop["loop"] == loop_number for each_loop in extracted["loops"]):
                    extracted["loops"].append({"loop": loop_number, "total": None, "p0": None, "p1": None, "p2": None, "found": False})
            finding_match = re.search(r"Total:\s*(\d+)\s*\(P0=(\d+),\s*P1=(\d+),\s*P2=(\d+)\)", text)
            if finding_match:
                total_findings, p0_count, p1_count, p2_count = map(int, finding_match.groups())
                for each_loop in reversed(extracted["loops"]):
                    if not each_loop["found"]:
                        each_loop.update({"total": total_findings, "p0": p0_count, "p1": p1_count, "p2": p2_count, "found": True})
                        break
            alt_finding_match = re.search(r"(\d+)\s+findings?\s+\(P0=(\d+),\s*P1=(\d+),\s*P2=(\d+)\)", text)
            if alt_finding_match:
                total_findings, p0_count, p1_count, p2_count = map(int, alt_finding_match.groups())
                for each_loop in reversed(extracted["loops"]):
                    if not each_loop["found"]:
                        each_loop.update({"total": total_findings, "p0": p0_count, "p1": p1_count, "p2": p2_count, "found": True})
                        break
            for each_marker in outcome_markers:
                if each_marker in text:
                    extracted["outcome"] = each_marker
            if re.search(r"\bconverged\b", text, re.I) and "PR #" in text:
                extracted["outcome"] = "converged"
            if re.search(r"re.?trigger.*bugbot|bugbot.*re.?trigger", text, re.I):
                extracted["bugbot_retriggers"] += 1
            if re.search(r"bugteam|/eval-bugteam", text, re.I):
                extracted["has_bugteam"] = True
            if re.search(r"pr-converge|/eval-pr-converge", text, re.I):
                extracted["has_pr_converge"] = True
    extracted["loops"].sort(key=lambda each_loop: each_loop["loop"])
    return extracted


def test_fix_regression(all_sessions: list[dict]) -> list[dict]:
    failures = []
    for each_session in all_sessions:
        totals = [(each_loop["loop"], each_loop["total"]) for each_loop in each_session["loops"] if each_loop["total"] is not None]
        for each_index in range(len(totals) - 1):
            first_loop_number, first_loop_total = totals[each_index]
            second_loop_number, second_loop_total = totals[each_index + 1]
            if second_loop_total > first_loop_total:
                failures.append({"session": each_session["name"], "pr": each_session["pr_numbers"], "detail": "L{}({}) > L{}({})".format(second_loop_number, second_loop_total, first_loop_number, first_loop_total)})
    return failures


def test_verified_clean_depth(all_sessions: list[dict]) -> list[dict]:
    all_shallow_patterns = ALL_SHALLOW_PATTERNS
    failures = []
    for each_session in all_sessions:
        with open(each_session["path"], "r", encoding="utf-8", errors="replace") as file_handle:
            for each_line in file_handle:
                each_line = each_line.strip()
                if not each_line:
                    continue
                try:
                    parsed_entry = json.loads(each_line)
                except json.JSONDecodeError:
                    continue
                text = extract_text(parsed_entry)
                if not ("verified_clean" in text.lower() or "<verified_clean" in text):
                    continue
                for each_pattern in all_shallow_patterns:
                    if each_pattern in text.lower():
                        failures.append({"session": each_session["name"], "pr": each_session["pr_numbers"], "detail": "Shallow verified-clean: '{}'".format(each_pattern)})
                        break
    return failures[:MAXIMUM_REPORT_COUNT]


def run_all_gap_tests(all_sessions: list[dict]) -> dict:
    return {
        "test_1_fix_regression": test_fix_regression(all_sessions),
        "test_4_verified_clean_depth": test_verified_clean_depth(all_sessions),
    }


def print_report(all_sessions: list[dict], all_gaps: dict) -> None:
    print("=" * HEADER_WIDTH)
    print("SESSION METRICS")
    print("=" * HEADER_WIDTH)
    for each_session in all_sessions:
        print("\n  {}".format(each_session["name"]))
        print("    PRs: {}  Repo: {}".format(each_session["pr_numbers"], each_session["repo"]))
        print("    Bugbot re-triggers: {}  Outcome: {}".format(each_session["bugbot_retriggers"], each_session["outcome"]))
        print("    Bugteam: {}  PR-Converge: {}".format(each_session["has_bugteam"], each_session["has_pr_converge"]))
        print("    Loops ({}):".format(len(each_session["loops"])))
        for each_loop in each_session["loops"]:
            mark = " Y" if each_loop["found"] else " N"
            print("      L{}: total={} P0={} P1={} P2={} found={}".format(each_loop["loop"], each_loop["total"], each_loop["p0"], each_loop["p1"], each_loop["p2"], mark))
    print("\n{}".format("=" * HEADER_WIDTH))
    print("GAP DETECTION TESTS")
    print("=" * HEADER_WIDTH)
    for each_test_name, each_failures in sorted(all_gaps.items()):
        print("\n  {}: ".format(each_test_name), end="")
        if not each_failures:
            print("PASS")
        elif len(each_failures) >= GAP_EVIDENCE_THRESHOLD:
            print("FAIL -- CONFIRMED ({} occurrences)".format(len(each_failures)))
            for each_failure in each_failures:
                print("    {} (PR {}): {}".format(each_failure["session"], each_failure["pr"], each_failure["detail"]))
        else:
            print("FAIL -- SINGLE OCCURRENCE ({}, not actionable)".format(len(each_failures)))
            for each_failure in each_failures:
                print("    {}: {}".format(each_failure["session"], each_failure["detail"]))


if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        print("Usage: python extract_bugteam_metrics.py <session.jsonl> [...]")
        sys.exit(1)
    all_sessions = []
    for each_path in paths:
        all_sessions.append(extract_session(each_path))
    all_gaps = run_all_gap_tests(all_sessions)
    print_report(all_sessions, all_gaps)
