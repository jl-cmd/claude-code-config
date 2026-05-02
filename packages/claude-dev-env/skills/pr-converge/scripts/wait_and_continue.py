"""Block for a fixed delay, then print a continuation file to stdout (UTF-8).

Used when the LLM harness has no ``ScheduleWakeup``: the agent writes an
injection file, runs this script in the foreground, then treats stdout as the
next user message so the same session continues pr-converge autonomously.
"""

import argparse
import sys
import time
from datetime import timedelta
from pathlib import Path


def wait_and_continue(*, delay_seconds: int, continuation_path: Path) -> None:
    """Sleep for ``delay_seconds``, then write file contents to stdout."""
    time.sleep(delay_seconds)
    payload = continuation_path.read_text(encoding="utf-8")
    sys.stdout.write(payload)
    if not payload.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()


def main() -> int:
    maximum_delay_seconds = int(timedelta(days=1).total_seconds())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delay-seconds",
        required=True,
        type=int,
        help="Seconds to block before emitting the continuation (use 60 or 270 per SKILL.md).",
    )
    parser.add_argument(
        "--continuation-file",
        required=True,
        dest="continuation_path",
        type=Path,
        help="UTF-8 file whose entire contents are printed to stdout after the delay.",
    )
    parsed = parser.parse_args(sys.argv[1:])
    continuation_path: Path = parsed.continuation_path
    delay_seconds: int = parsed.delay_seconds
    if delay_seconds < 0 or delay_seconds > maximum_delay_seconds:
        print(
            f"error: --delay-seconds must be between 0 and {maximum_delay_seconds} inclusive",
            file=sys.stderr,
        )
        return 2
    if not continuation_path.is_file():
        print(f"error: continuation file not found: {continuation_path}", file=sys.stderr)
        return 2
    wait_and_continue(
        delay_seconds=delay_seconds,
        continuation_path=continuation_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
