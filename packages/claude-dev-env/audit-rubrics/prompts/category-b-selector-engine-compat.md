Audit jl-cmd/claude-code-config PR #394 for **Category B only** (selector / query / engine compatibility). Skip A, C–K. Sub-bucket forced-exhaustion mode: Category B is decomposed into 7 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**B1. CSS / DOM selector vs target browser engine**
- The diff contains no CSS, no HTML, no JavaScript, no DOM-related code.
- Shape B proof-of-absence expected. Adversarial probes must verify: zero CSS selectors anywhere in the four files; zero references to `document.querySelector` / jQuery / shadow DOM; zero rendered-output assertions in tests.

**B2. SQL syntax vs database version**
- The diff contains no database access, no migrations, no ORM models.
- Shape B proof-of-absence expected. Adversarial probes must verify: no `import sqlite3` / `import psycopg2` / SQLAlchemy / Django ORM; no SQL string literals; no schema/migration files added.

**B3. Regex syntax vs engine flavor / f-string-built patterns**
- The test helper at `tests/test_sweep_empty_dirs.py` line 117–124 builds a PowerShell command via Python f-string interpolation: `f"(Get-Item '{path}').CreationTimeUtc = [DateTime]'{date_str}'"`. The interpolated `path` and `date_str` values pass through Python → argv → PowerShell `-Command` parsing.
- Adversarial concern: PowerShell single-quote string literal (`'…'`) does not honor backslash escapes but treats `''` as an embedded single quote. If `path` contains a single quote (e.g., a directory named `won't`), the resulting command becomes syntactically broken.
- Adversarial concern: PowerShell double-quoted strings perform variable expansion via `$`. The current code uses single quotes around `{path}`, but a directory containing `$(...)` inside a single-quoted PS string is still inert — verify.
- Adversarial concern: backticks in the path are PowerShell escape characters inside double-quoted strings; inert inside single-quoted strings — verify.
- Adversarial concern: the date format string `"%Y-%m-%d %H:%M:%S"` and `[DateTime]'{date_str}'` parsing — does PowerShell's `[DateTime]` accept this exact ISO-8601-without-T format across PS 5.1 and PS 7+, or is locale-dependent parsing a hazard?

**B4. Shell / CLI / cmdlet syntax vs runtime version**
- The PowerShell installer at `Install-SweepEmptyDirs.ps1` uses the ScheduledTasks module: `Get-ScheduledTask`, `New-ScheduledTaskTrigger`, `New-ScheduledTaskAction`, `New-ScheduledTaskSettingsSet`, `Register-ScheduledTask`, `Unregister-ScheduledTask`. The ScheduledTasks module is Windows-only — not available on PowerShell Core running on Linux/macOS.
- The shebang `#!/usr/bin/env pwsh` declares PowerShell 7+ as the interpreter, but the script also targets Windows-only cmdlets — confirm whether PS 7+ on Windows ships the ScheduledTasks module by default vs requiring the Windows Compatibility shim.
- `New-ScheduledTaskTrigger -Daily -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)` — verify `-RepetitionInterval` is valid for the `-Daily` parameter set across PS 5.1 (Windows PowerShell 5.1 ships `ScheduledTasks` module v1.0.0.0) and PS 7+ (Windows). Microsoft docs: https://learn.microsoft.com/powershell/module/scheduledtasks/new-scheduledtasktrigger.
- `New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable` — confirm all three switches exist in the `ScheduledTasks` v1.0.0.0 module shipped with Windows 8.1 / Server 2012 R2 baseline (the lowest Windows that ships PS 5.1).
- The Python test helper invokes `["powershell", "-Command", …]` — `powershell` resolves to Windows PowerShell 5.1 on Windows, but does not exist on Linux/macOS. The PR's Python test will fail to run cross-platform; confirm whether the tests are gated to Windows-only via pytest markers or sys.platform checks (they are not — ad-hoc adversarial probe).
- The `param(...)` block uses `ParameterSetName=` without `[CmdletBinding(DefaultParameterSetName=...)]`. With no default set, a no-argument invocation of the script triggers PowerShell's parameter-set ambiguity error. Behavior differs subtly across PS 5.1 and PS 7+ — verify the error message and exit code shape match what the user's automation expects.

**B5. JSON path / XPath / structural query vs library**
- The diff contains no JSON path expressions, no XPath, no structural queries.
- Shape B proof-of-absence expected. Adversarial probes must verify: no `jq` invocations; no `jsonpath_ng` / `lxml` / `xml.etree` usage; no JSON-pointer (`/foo/bar`) string literals.

**B6. Search query DSL vs engine**
- The diff contains no search queries, no Lucene / Elasticsearch / Zoekt / OpenSearch DSL.
- Shape B proof-of-absence expected. Adversarial probes must verify: no HTTP calls to `/_search` endpoints; no query-string DSL fragments; no `match`/`bool`/`should` clause objects.

**B7. ORM vs raw SQL semantic differences**
- The diff contains no ORM usage and no raw SQL.
- Shape B proof-of-absence expected. Adversarial probes must verify: no SQLAlchemy / Django ORM / Peewee imports; no `.filter()` / `.filter_by()` / `Q()` expressions; no transaction context managers tied to an ORM.

## Cross-bucket questions to answer at the end

Q1: Are there any compatibility constraints that span two sub-buckets that single-bucket analysis would miss (e.g., the f-string-built PowerShell command at `test_sweep_empty_dirs.py:120-123` crosses B3 (Python f-string interpolation safety) and B4 (PowerShell runtime version) — the same line is exposed to both axes)?
Q2: What's the worst engine-incompatibility hazard introduced by this PR? Cite file:line.
Q3: Where would a future engine/library upgrade most likely break a cmdlet, command line, or interpolated pattern in this diff? Name the line(s) most fragile.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket B1–B7, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 incompatibility bugs across these 7 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

## Diff (4 new files, all lines in scope)

### packages/claude-dev-env/scripts/sweep_empty_dirs.py
```python
#!/usr/bin/env python3
"""Delete empty directories older than 2 minutes under a given root."""

import argparse
import os
import sys
import time

from config.sweep_config import DEFAULT_AGE_SECONDS
from config.sweep_config import DEFAULT_POLL_INTERVAL


def _log_walk_error(os_error: OSError) -> None:
    print(f"warning: cannot scan {os_error.filename} — {os_error.strerror}", file=sys.stderr)


def sweep(root: str, min_age_seconds: int) -> list[str]:
    """Remove empty directories under *root* older than *min_age_seconds*."""

    now = time.time()
    removed: list[str] = []

    for each_directory_path, _, _ in os.walk(
        root, onerror=_log_walk_error, topdown=False
    ):
        try:
            created = os.path.getctime(each_directory_path)
        except OSError:
            continue
        if now - created >= min_age_seconds:
            try:
                os.rmdir(each_directory_path)
                print(f"deleted: {each_directory_path}")
                removed.append(each_directory_path)
            except OSError:
                pass

    return removed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Delete empty directories older than a given age.")
    parser.add_argument("root", help="Root directory to scan")
    parser.add_argument("--age", type=int, default=DEFAULT_AGE_SECONDS,
                        help=f"Minimum age in seconds (default: {DEFAULT_AGE_SECONDS} = 2 minutes)")
    parser.add_argument("--once", action="store_true",
                        help="Single pass and exit instead of watching in a loop")
    parser.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL,
                        help=f"Poll interval in seconds when looping (default: {DEFAULT_POLL_INTERVAL})")
    return parser


def main() -> None:
    parser = _build_parser()
    arguments = parser.parse_args()

    if not os.path.isdir(arguments.root):
        print(f"error: not a directory: {arguments.root}", file=sys.stderr)
        sys.exit(1)

    if arguments.once:
        sweep(arguments.root, arguments.age)
        return

    print(f"watching {arguments.root} every {arguments.interval}s (age threshold: {arguments.age}s)")
    try:
        while True:
            sweep(arguments.root, arguments.age)
            time.sleep(arguments.interval)
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
```

### packages/claude-dev-env/scripts/config/sweep_config.py
```python
"""Centralized timing configuration for sweep_empty_dirs."""

DEFAULT_AGE_SECONDS: int = 120
DEFAULT_POLL_INTERVAL: int = 30
```

### packages/claude-dev-env/scripts/tests/test_sweep_empty_dirs.py
```python
"""Tests for sweep_empty_dirs.py"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sweep_empty_dirs import sweep  # noqa: E402


def _set_creation_time_windows(path: str, timestamp: float) -> None:
    dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    subprocess.run(
        ["powershell", "-Command",
         f"(Get-Item '{path}').CreationTimeUtc = [DateTime]'{date_str}'"],
        check=True, capture_output=True,
    )


def test_deletes_empty_dir_older_than_threshold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        empty_dir = os.path.join(tmp, "old_empty")
        os.mkdir(empty_dir)
        _set_creation_time_windows(empty_dir, time.time() - 300)
        removed = sweep(tmp, min_age_seconds=120)
        assert empty_dir in removed
        assert not os.path.isdir(empty_dir)


def test_skips_empty_dir_newer_than_threshold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fresh_dir = os.path.join(tmp, "fresh_empty")
        os.mkdir(fresh_dir)
        removed = sweep(tmp, min_age_seconds=120)
        assert fresh_dir not in removed
        assert os.path.isdir(fresh_dir)


def test_deletes_nested_empty_dirs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        leaf = os.path.join(tmp, "parent", "child", "leaf")
        os.makedirs(leaf)
        _set_creation_time_windows(os.path.join(tmp, "parent"), time.time() - 300)
        _set_creation_time_windows(os.path.join(tmp, "parent", "child"), time.time() - 300)
        _set_creation_time_windows(leaf, time.time() - 300)
        removed = sweep(tmp, min_age_seconds=120)
        assert leaf in removed
        assert os.path.join(tmp, "parent", "child") in removed
        assert os.path.join(tmp, "parent") in removed


def test_empty_root_does_not_crash() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _set_creation_time_windows(tmp, time.time() - 300)
        sweep(tmp, min_age_seconds=120)


def test_skips_nonempty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        nonempty_dir = os.path.join(tmp, "has_stuff")
        os.mkdir(nonempty_dir)
        Path(nonempty_dir, "keepme.txt").write_text("hello")
        removed = sweep(tmp, min_age_seconds=0)
        assert nonempty_dir not in removed
        assert os.path.isdir(nonempty_dir)
```

### packages/claude-dev-env/scripts/Install-SweepEmptyDirs.ps1
```powershell
#!/usr/bin/env pwsh
param(
    [Parameter(ParameterSetName = "install")]
    [string]$Target,

    [Parameter(ParameterSetName = "install")]
    [int]$IntervalMinutes = 5,

    [Parameter(ParameterSetName = "install")]
    [int]$AgeSeconds = 120,

    [Parameter(ParameterSetName = "remove")]
    [switch]$Remove,

    [Parameter(ParameterSetName = "status")]
    [switch]$Status
)

$TaskName = "SweepEmptyDirs"

if ($Status) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Host "STATUS: $TaskName is not registered."
        return
    }
    Write-Host "STATUS: $TaskName is registered."
    Write-Host "  State: $($task.State)"
    Write-Host "  Actions:"
    foreach ($action in $task.Actions) {
        Write-Host "    $($action.Execute) $($action.Arguments)"
    }
    Write-Host "  Triggers:"
    foreach ($trigger in $task.Triggers) {
        Write-Host "    $($trigger.Repetition.Interval) (starting $($trigger.StartBoundary))"
    }
    return
}

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "$TaskName removed."
    return
}

$ScriptDir = Split-Path -Parent $PSCommandPath
$ScriptPath = Join-Path $ScriptDir "sweep_empty_dirs.py"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "sweep_empty_dirs.py not found at: $ScriptPath"
    exit 1
}

if (-not $Target) {
    Write-Error "Parameter -Target is required (the directory to watch)."
    exit 1
}

if (-not (Test-Path $Target)) {
    Write-Error "Target directory does not exist: $Target"
    exit 1
}

$_py = Get-Command py -ErrorAction SilentlyContinue
$PythonPath = if ($_py) { $_py.Source } else { (Get-Command python).Source }
if (-not $PythonPath) {
    Write-Error "Cannot find Python (py or python) on PATH."
    exit 1
}
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "$ScriptPath --once --age $AgeSeconds ""$Target"""
$Trigger = New-ScheduledTaskTrigger -Daily -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "$TaskName registered — runs every ${IntervalMinutes}min against '$Target' (age ≥ ${AgeSeconds}s)."
```
