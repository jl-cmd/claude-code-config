"""One-shot runner: marker scan + extraction + gap detection.

Usage:
    python run_self_improve.py <session.jsonl> [<more_sessions...>]

Outputs a JSON report to stdout with:
  - sessions_scanned: count
  - markers_found: per-file matched markers
  - session_metrics: per-session loop/finding data
  - gap_tests: per-test pass/fail/confirmed status

Dies on first error with a clear message.
"""

import json
import os
import sys
from pathlib import Path


def _ensure_scripts_on_path() -> None:
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)


_ensure_scripts_on_path()

from scan_session_markers import scan_file  # noqa: E402
from extract_bugteam_metrics import (  # noqa: E402
    extract_session,
    run_all_gap_tests,
    GAP_EVIDENCE_THRESHOLD,
)
from config.constants import HEADER_WIDTH, JSON_INDENT_WIDTH  # noqa: E402


def main() -> None:
    all_paths = sys.argv[1:]
    if not all_paths:
        print(
            "Usage: python run_self_improve.py <session.jsonl> [<more_sessions...>]",
            file=sys.stderr,
        )
        sys.exit(1)

    for each_path in all_paths:
        if not os.path.isfile(each_path):
            print(f"ERROR: File not found: {each_path}", file=sys.stderr)
            sys.exit(1)

    print("=== Step 1: Marker scanning ===", file=sys.stderr)
    all_marker_results = []
    for each_path in all_paths:
        each_result = scan_file(each_path)
        all_marker_results.append(each_result)
        name = Path(each_path).stem
        size_mb = each_result["size_bytes"] / (1024 * 1024)
        if each_result["matched_markers"]:
            print(
                f"  {name}: {size_mb:.1f}MB, markers={each_result['matched_markers']}",
                file=sys.stderr,
            )
        elif each_result["error"]:
            print(f"  {name}: ERROR - {each_result['error']}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"  {name}: {size_mb:.1f}MB, no markers", file=sys.stderr)

    matched_paths = [
        each["path"] for each in all_marker_results if each["matched_markers"]
    ]
    print(
        f"\n  Matched: {len(matched_paths)}/{len(all_paths)} sessions", file=sys.stderr
    )

    if not matched_paths:
        print(
            json.dumps(
                {
                    "status": "no-action",
                    "reason": "No bugteam/pr-converge markers found in any session.",
                    "sessions_scanned": len(all_paths),
                    "markers_found": all_marker_results,
                },
                indent=JSON_INDENT_WIDTH,
            )
        )
        return

    print("\n=== Step 2: Extraction ===", file=sys.stderr)
    all_sessions = []
    for each_path in matched_paths:
        each_session = extract_session(each_path)
        all_sessions.append(each_session)
        name = each_session["name"]
        pr_list = each_session["pr_numbers"]
        print(
            f"  {name}: PRs={pr_list}, loops={len(each_session['loops'])}, outcome={each_session['outcome']}",
            file=sys.stderr,
        )

    print("\n=== Step 3: Gap-detection tests ===", file=sys.stderr)
    all_gaps = run_all_gap_tests(all_sessions)
    report_parts = []
    confirmed = 0
    single_occurrences = []
    for each_test_name, each_failures in sorted(all_gaps.items()):
        if not each_failures:
            report_parts.append(
                {"test": each_test_name, "status": "pass", "failures": []}
            )
            print(f"  {each_test_name}: PASS", file=sys.stderr)
        elif len(each_failures) >= GAP_EVIDENCE_THRESHOLD:
            report_parts.append(
                {
                    "test": each_test_name,
                    "status": "confirmed",
                    "failures": each_failures,
                }
            )
            confirmed += 1
            print(
                f"  {each_test_name}: CONFIRMED ({len(each_failures)} occurrences)",
                file=sys.stderr,
            )
            for each_f in each_failures:
                print(
                    f"    {each_f['session']} (PR {each_f['pr']}): {each_f['detail']}",
                    file=sys.stderr,
                )
        else:
            report_parts.append(
                {
                    "test": each_test_name,
                    "status": "single_occurrence",
                    "failures": each_failures,
                }
            )
            single_occurrences.extend(each_failures)
            print(
                f"  {each_test_name}: SINGLE OCCURRENCE ({len(each_failures)}, not actionable)",
                file=sys.stderr,
            )

    print(f"\n  Confirmed gaps: {confirmed}", file=sys.stderr)
    print(f"  Single occurrences: {len(single_occurrences)}", file=sys.stderr)
    print(
        f"  Note: Tests 2, 3, 5 are not implemented in the extraction script.",
        file=sys.stderr,
    )

    report_output = {
        "status": "actionable" if confirmed else "no-action",
        "confirmed_gap_count": confirmed,
        "sessions_scanned": len(all_paths),
        "candidate_sessions": len(matched_paths),
        "markers_found": [
            {
                "name": Path(e["path"]).stem,
                "size_bytes": e["size_bytes"],
                "matched_markers": e["matched_markers"],
            }
            for e in all_marker_results
        ],
        "session_metrics": [
            {
                "name": s["name"],
                "pr_numbers": s["pr_numbers"],
                "repo": s["repo"],
                "loops": s["loops"],
                "bugbot_retriggers": s["bugbot_retriggers"],
                "outcome": s["outcome"],
                "has_bugteam": s["has_bugteam"],
                "has_pr_converge": s["has_pr_converge"],
            }
            for s in all_sessions
        ],
        "gap_tests": report_parts,
        "single_occurrences": single_occurrences,
        "note": "Tests 2, 3, 5 not implemented in extraction script",
    }

    print(file=sys.stderr)
    print("=" * HEADER_WIDTH, file=sys.stderr)
    print("FULL REPORT (stdout)", file=sys.stderr)
    print("=" * HEADER_WIDTH, file=sys.stderr)
    print(json.dumps(report_output, indent=JSON_INDENT_WIDTH))


if __name__ == "__main__":
    main()
