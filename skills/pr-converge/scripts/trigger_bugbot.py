"""Post a `bugbot run` comment to re-trigger a Cursor Bugbot review.

Writes the literal trigger phrase to a temp file (per the gh-body-file rule —
`gh pr comment --body "..."` may corrupt backticks), invokes
`gh pr comment --body-file`, and removes the temp file on success or failure.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.modules.pop("config", None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.pr_converge_constants import (
    BUGBOT_RUN_TEMPFILE_PREFIX,
    BUGBOT_RUN_TEMPFILE_SUFFIX,
    BUGBOT_RUN_TRIGGER_PHRASE,
)


def trigger_bugbot(*, owner: str, repo: str, number: int) -> str:
    """Post the bugbot re-trigger comment, return the comment URL gh emits."""
    trigger_phrase = BUGBOT_RUN_TRIGGER_PHRASE
    file_descriptor, raw_path = tempfile.mkstemp(
        suffix=BUGBOT_RUN_TEMPFILE_SUFFIX, prefix=BUGBOT_RUN_TEMPFILE_PREFIX
    )
    os.close(file_descriptor)
    body_file_path = Path(raw_path)
    body_file_path.write_text(trigger_phrase, encoding="utf-8")
    try:
        gh_command: list[str] = [
            "gh",
            "pr",
            "comment",
            str(number),
            "--repo",
            f"{owner}/{repo}",
            "--body-file",
            str(body_file_path),
        ]
        completed = subprocess.run(
            gh_command,
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        body_file_path.unlink(missing_ok=True)
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    comment_url = trigger_bugbot(
        owner=parsed_arguments.owner, repo=parsed_arguments.repo, number=parsed_arguments.number
    )
    sys.stdout.write(f"{comment_url}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
