#!/usr/bin/env python3
"""Delete empty directories older than 2 minutes under a given root.

Usage:
    python sweep_empty_dirs.py /path/to/watch
    python sweep_empty_dirs.py /path/to/watch --age 300
    python sweep_empty_dirs.py /path/to/watch --once
"""

import argparse
import os
import sys
import time

from config.sweep_config import DEFAULT_AGE_SECONDS
from config.sweep_config import DEFAULT_POLL_INTERVAL


def _positive_int(value: str) -> int:
    """Argparse type: require value >= 1."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {value}")
    return parsed


def _log_walk_error(os_error: OSError) -> None:
    print(f"warning: cannot scan {os_error.filename} — {os_error.strerror}", file=sys.stderr)


def sweep(root: str, min_age_seconds: int) -> list[str]:
    """Remove empty directories under *root* older than *min_age_seconds*.

    Walks bottom-up so nested empty directories are cleaned from the leaves
    inward.  Relies on os.rmdir to fail harmlessly for non-empty directories
    instead of checking snapshotted subdirectory lists.
    """

    removed: list[str] = []

    for each_directory_path, _, _ in os.walk(
        root, onerror=_log_walk_error, topdown=False
    ):
        now = time.time()
        try:
            created = os.path.getctime(each_directory_path)
        except FileNotFoundError:
            continue
        except PermissionError:
            print(f"warning: permission denied — {each_directory_path}", file=sys.stderr)
            continue
        if now - created > min_age_seconds:
            try:
                os.rmdir(each_directory_path)
                print(f"deleted: {each_directory_path}")
                removed.append(each_directory_path)
            except FileNotFoundError:
                pass
            except OSError:
                print(f"warning: could not remove {each_directory_path}", file=sys.stderr)

    return removed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete empty directories older than a given age.",
    )
    parser.add_argument("root", help="Root directory to scan")
    parser.add_argument(
        "--age",
        type=int,
        default=DEFAULT_AGE_SECONDS,
        help=f"Minimum age in seconds (default: {DEFAULT_AGE_SECONDS} = 2 minutes)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Single pass and exit instead of watching in a loop",
    )
    parser.add_argument(
        "--interval",
        type=_positive_int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Poll interval in seconds when looping (default: {DEFAULT_POLL_INTERVAL})",
    )
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

    print(
        f"watching {arguments.root} every {arguments.interval}s"
        f" (age threshold: {arguments.age}s)"
    )
    try:
        while True:
            sweep(arguments.root, arguments.age)
            time.sleep(arguments.interval)
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
