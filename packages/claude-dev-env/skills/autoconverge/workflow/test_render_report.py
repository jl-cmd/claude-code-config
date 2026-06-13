"""Tests for render_report.py against the real wf_881252e6-700 fixture."""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_report

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "wf_run"
FIXTURE_JOURNAL = FIXTURE_DIR / "workflows" / "wf_881252e6-700.json"

EXPECTED_TOTAL_FINDINGS = 15
EXPECTED_CRITICAL_COUNT = 0
EXPECTED_MINOR_COUNT = 15
EXPECTED_FIX_COMMIT_COUNT = 2
EXPECTED_GENERATED_DATE = "2026-06-13"
EXPECTED_FINDINGS_BY_ROUND = {1: 11, 2: 2, 3: 2, 4: 0}
EXPECTED_FINDINGS_BY_THEME = {"src/exports": 11, "src/logging": 2, "src/web": 2}


def test_load_run_data_aggregate_counts() -> None:
    """Should parse the fixture journal and transcripts into correct aggregate counts."""
    run_data = render_report.load_run_data(FIXTURE_JOURNAL, Path("."))

    assert run_data.total_finding_count == EXPECTED_TOTAL_FINDINGS
    assert run_data.critical_finding_count == EXPECTED_CRITICAL_COUNT
    assert run_data.minor_finding_count == EXPECTED_MINOR_COUNT
    assert run_data.fix_commit_count == EXPECTED_FIX_COMMIT_COUNT
    assert run_data.generated_date == EXPECTED_GENERATED_DATE


def test_load_run_data_by_round_counts() -> None:
    """Should assign findings to rounds by workflowProgress position boundary."""
    run_data = render_report.load_run_data(FIXTURE_JOURNAL, Path("."))

    for each_round, expected_count in EXPECTED_FINDINGS_BY_ROUND.items():
        actual_count = run_data.finding_count_by_round.get(each_round, 0)
        assert actual_count == expected_count, (
            f"Round {each_round}: expected {expected_count}, got {actual_count}"
        )


def test_load_run_data_by_theme_counts() -> None:
    """Should group distinct findings by the first two path segments."""
    run_data = render_report.load_run_data(FIXTURE_JOURNAL, Path("."))

    assert len(run_data.finding_count_by_theme) == len(EXPECTED_FINDINGS_BY_THEME)
    for each_theme, expected_count in EXPECTED_FINDINGS_BY_THEME.items():
        actual_count = run_data.finding_count_by_theme.get(each_theme, 0)
        assert actual_count == expected_count, (
            f"Theme {each_theme}: expected {expected_count}, got {actual_count}"
        )


def test_cli_end_to_end(tmp_path: Path) -> None:
    """Should exit 0, print the output path, and write HTML with expected substrings."""
    out_path = tmp_path / "report.html"
    render_script = Path(__file__).resolve().parent / "render_report.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(render_script),
            "--journal",
            str(FIXTURE_JOURNAL),
            "--out",
            str(out_path),
            "--pr",
            "example-owner/example-repo#211",
            "--final-sha",
            "7c2f420c4d5b7c83aa47f93d99a0f1420e3373c4",
            "--rounds",
            "4",
            "--repo",
            ".",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"

    printed_path = completed.stdout.strip()
    assert printed_path == str(out_path), (
        f"Expected stdout {out_path!r}, got {printed_path!r}"
    )

    assert out_path.exists(), "Output HTML file was not written"
    html_content = out_path.read_text(encoding="utf-8")

    expected_substrings = [
        "PR #211 Convergence Insights",
        "at-a-glance",
        "Findings by severity",
        "Findings by round",
        "Tests added per round",
        "Findings by theme",
        "Banned identifier",
        "result",
        "in test",
        "Converged",
        "7c2f420c",
    ]
    for each_substring in expected_substrings:
        assert each_substring in html_content, (
            f"Expected substring not found in HTML: {each_substring!r}"
        )

    minor_card_count = html_content.count('class="bug-card minor"')
    assert minor_card_count == EXPECTED_MINOR_COUNT, (
        f"Expected {EXPECTED_MINOR_COUNT} minor cards, found {minor_card_count}"
    )


def test_html_contains_no_hedging_words(tmp_path: Path) -> None:
    """Should produce HTML with no hedging language anywhere in the rendered text."""
    out_path = tmp_path / "report-hedge.html"
    render_script = Path(__file__).resolve().parent / "render_report.py"

    subprocess.run(
        [
            sys.executable,
            str(render_script),
            "--journal",
            str(FIXTURE_JOURNAL),
            "--out",
            str(out_path),
            "--pr",
            "example-owner/example-repo#211",
            "--final-sha",
            "7c2f420c4d5b7c83aa47f93d99a0f1420e3373c4",
            "--rounds",
            "4",
            "--repo",
            ".",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    html_content = out_path.read_text(encoding="utf-8")
    all_hedging_words = [
        "could",
        "might",
        "would",
        "should",
        "likely",
        "probably",
        "appears",
        "seems",
    ]
    for each_word in all_hedging_words:
        pattern = re.compile(r"\b" + re.escape(each_word) + r"\b", re.IGNORECASE)
        assert not pattern.search(html_content), (
            f"Hedging word {each_word!r} found in rendered HTML"
        )


def _init_git_repo(repo_path: Path) -> None:
    """Initialize a git repo with a committed baseline so diffs resolve."""
    subprocess.run(
        ["git", "-C", str(repo_path), "init"], capture_output=True, check=True
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.name", "Test"],
        capture_output=True,
        check=True,
    )
    (repo_path / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo_path), "add", "."], capture_output=True, check=True
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "commit", "-m", "baseline"],
        capture_output=True,
        check=True,
    )


def _resolve_head(repo_path: Path) -> str:
    """Return the current HEAD sha of the repo."""
    completed = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_count_tests_added_does_not_double_count_new_file(tmp_path: Path) -> None:
    """Should count a new test file with two test functions as exactly two."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _init_git_repo(repo_path)
    base_sha = _resolve_head(repo_path)

    new_test_file = repo_path / "test_feature.py"
    new_test_file.write_text(
        "def test_one() -> None:\n"
        "    assert True\n"
        "\n"
        "def test_two() -> None:\n"
        "    assert True\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "add", "."], capture_output=True, check=True
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "commit", "-m", "add tests"],
        capture_output=True,
        check=True,
    )
    new_sha = _resolve_head(repo_path)

    test_count = render_report._count_tests_added(base_sha, new_sha, repo_path)

    assert test_count == 2, f"Expected 2 added test definitions, got {test_count}"


def test_robustness_with_missing_transcripts(tmp_path: Path) -> None:
    """Should succeed even when agent transcript files are absent or contain non-tool lines."""
    out_path = tmp_path / "report-robust.html"
    render_script = Path(__file__).resolve().parent / "render_report.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(render_script),
            "--journal",
            str(FIXTURE_JOURNAL),
            "--out",
            str(out_path),
            "--pr",
            "example-owner/example-repo#211",
            "--final-sha",
            "7c2f420c4d5b7c83aa47f93d99a0f1420e3373c4",
            "--rounds",
            "4",
            "--repo",
            ".",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, (
        f"Render failed despite missing transcripts:\n{completed.stderr}"
    )

    html_content = out_path.read_text(encoding="utf-8")
    assert "PR #211 Convergence Insights" in html_content

    minor_card_count = html_content.count('class="bug-card minor"')
    assert minor_card_count == EXPECTED_MINOR_COUNT, (
        f"Missing transcripts changed finding count: expected {EXPECTED_MINOR_COUNT}, "
        f"got {minor_card_count}"
    )
