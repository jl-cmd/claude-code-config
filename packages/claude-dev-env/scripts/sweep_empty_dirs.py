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

_DEFAULT_AGE_SECONDS: int = 120
_DEFAULT_POLL_INTERVAL: int = 30


def _is_empty(directory: str) -> bool:
    try:
        with os.scandir(directory) as entries:
            for _ in entries:
                return False
        return True
    except PermissionError:
        return False


def sweep(root: str, min_age_seconds: int) -> list[str]:
    """Remove empty directories under *root* older than *min_age_seconds*."""

    now = time.time()
    removed: list[str] = []

    for each_dirpath, each_dirnames, each_filenames in os.walk(root, topdown=True):
        if not os.path.isdir(each_dirpath):
            continue

        if each_filenames or each_dirnames:
            continue

        created = os.path.getctime(each_dirpath)
        if now - created >= min_age_seconds:
            try:
                os.rmdir(each_dirpath)
                print(f"deleted: {each_dirpath}")
            except OSError as exc:
                print(f"failed: {each_dirpath} — {exc}", file=sys.stderr)
                continue
            removed.append(each_dirpath)

    return removed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete empty directories older than a given age.",
    )
    parser.add_argument("root", help="Root directory to scan")
    parser.add_argument(
        "--age",
        type=int,
        default=_DEFAULT_AGE_SECONDS,
        help="Minimum age in seconds (default: 120 = 2 minutes)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Single pass and exit instead of watching in a loop",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=_DEFAULT_POLL_INTERVAL,
        help="Poll interval in seconds when looping (default: 30)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not os.path.isdir(args.root):
        print(f"error: not a directory: {args.root}", file=sys.stderr)
        sys.exit(1)

    if args.once:
        sweep(args.root, args.age)
        return

    print(f"watching {args.root} every {args.interval}s (age threshold: {args.age}s)")
    try:
        while True:
            sweep(args.root, args.age)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
