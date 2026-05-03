"""Resolve the per-tick mergeability state of the current PR.

Wraps ``gh pr view --json mergeable,mergeStateStatus,headRefOid`` so the skill
body emits one script invocation. Single-object endpoint - no pagination.
The returned dict gates pr-converge's mark-ready step against PRs whose base
branch state is DIRTY (conflicts) or otherwise non-CLEAN.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import MERGEABILITY_FIELDS


def check_pr_mergeability() -> dict[str, object]:
    """Return ``{mergeable, mergeStateStatus, headRefOid}`` from ``gh pr view``."""
    gh_command: list[str] = ["gh", "pr", "view", "--json", MERGEABILITY_FIELDS]
    completed = subprocess.run(
        gh_command,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return json.loads(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    mergeability_state = check_pr_mergeability()
    json.dump(mergeability_state, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
