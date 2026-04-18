from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def resolve_claude_dev_env_root() -> Path:
    environment_value = (Path(__file__).resolve().parents[3]).resolve()
    return environment_value


def load_validate_content():
    package_root = resolve_claude_dev_env_root()
    enforcer_path = package_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    if not enforcer_path.is_file():
        message = f"bugteam_code_rules_gate: missing enforcer at {enforcer_path}"
        print(message, file=sys.stderr)
        raise SystemExit(2)
    specification = importlib.util.spec_from_file_location(
        "code_rules_enforcer",
        enforcer_path,
    )
    if specification is None or specification.loader is None:
        print("bugteam_code_rules_gate: could not load code_rules_enforcer.", file=sys.stderr)
        raise SystemExit(2)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.validate_content


def paths_from_git_diff(repository_root: Path, base_reference: str) -> list[Path]:
    merge_result = subprocess.run(
        ["git", "merge-base", "HEAD", base_reference],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if merge_result.returncode != 0:
        print(
            f"bugteam_code_rules_gate: git merge-base HEAD {base_reference} failed:\n"
            f"{merge_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    merge_base = merge_result.stdout.strip()
    name_result = subprocess.run(
        ["git", "diff", "--name-only", f"{merge_base}..HEAD"],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if name_result.returncode != 0:
        print(
            f"bugteam_code_rules_gate: git diff --name-only failed:\n{name_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    relative_paths = [line.strip() for line in name_result.stdout.splitlines() if line.strip()]
    return [repository_root / relative_path for relative_path in relative_paths]


def is_code_path(file_path: Path) -> bool:
    suffix = file_path.suffix.lower()
    return suffix in {".py", ".js", ".ts", ".tsx", ".jsx"}


def run_gate(
    validate_content,
    file_paths: list[Path],
    repository_root: Path,
) -> int:
    total_issues = 0
    for file_path in sorted(set(file_paths)):
        try:
            resolved = file_path.resolve()
        except OSError:
            continue
        try:
            resolved.relative_to(repository_root.resolve())
        except ValueError:
            continue
        if not is_code_path(resolved):
            continue
        if not resolved.is_file():
            continue
        try:
            content = resolved.read_text(encoding="utf-8")
        except OSError:
            print(f"bugteam_code_rules_gate: skip unreadable {resolved}", file=sys.stderr)
            continue
        relative = resolved.relative_to(repository_root.resolve())
        issues = validate_content(content, str(relative).replace("\\", "/"), old_content=content)
        if issues:
            total_issues += len(issues)
            print(f"{relative}:", file=sys.stderr)
            for issue in issues:
                print(f"  {issue}", file=sys.stderr)
    if total_issues:
        print(
            f"bugteam_code_rules_gate: {total_issues} violation(s) reported.",
            file=sys.stderr,
        )
        return 1
    return 0


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run CODE_RULES validators (validate_content) on files in the working tree. "
            "Default file set: git diff --name-only merge-base(base)..HEAD."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: cwd).",
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Merge-base ref for git diff (default: origin/main).",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional explicit files; if set, git diff is not used.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    repository_root = (
        arguments.repo_root.resolve()
        if arguments.repo_root is not None
        else Path.cwd().resolve()
    )
    validate_content = load_validate_content()
    if arguments.paths:
        file_paths = [repository_root / path for path in arguments.paths]
    else:
        file_paths = paths_from_git_diff(repository_root, arguments.base)
    return run_gate(validate_content, file_paths, repository_root)


if __name__ == "__main__":
    raise SystemExit(main())
