#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from pathlib import Path

PYTHON_EXTENSIONS = {".py"}
JS_EXTENSIONS = {".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"}
JSON_EXTENSIONS = {".json"}
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOKS_DIR = os.path.join(PLUGIN_ROOT, "hooks") + os.sep
PYTHON_FORMAT_TIMEOUT_SECONDS = 15
JS_FORMAT_TIMEOUT_SECONDS = 30
PRETTIER_CONFIG_NAMES = {
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.yml",
    ".prettierrc.yaml",
    ".prettierrc.js",
    ".prettierrc.cjs",
    ".prettierrc.mjs",
    ".prettierrc.toml",
    "prettier.config.js",
    "prettier.config.cjs",
    "prettier.config.mjs",
}


def has_prettier_config(file_path: str) -> bool:
    each_ancestor = Path(file_path).resolve().parent
    while True:
        for config_name in PRETTIER_CONFIG_NAMES:
            if (each_ancestor / config_name).exists():
                return True
        parent = each_ancestor.parent
        if parent == each_ancestor:
            break
        each_ancestor = parent
    return False


def is_untracked_in_git(file_path: str) -> bool:
    """Check if file is untracked (brand new) by git."""
    containing_directory = str(Path(file_path).parent)
    try:
        git_check = subprocess.run(
            ["git", "ls-files", "--error-unmatch", file_path],
            capture_output=True,
            text=True,
            cwd=containing_directory,
            timeout=5,
        )
        return git_check.returncode != 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    file_path = hook_input.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    if tool_name == "Edit":
        sys.exit(0)

    if tool_name == "Write" and not is_untracked_in_git(file_path):
        sys.exit(0)

    if file_path.startswith(HOOKS_DIR):
        sys.exit(0)

    suffix = Path(file_path).suffix.lower()

    if suffix in PYTHON_EXTENSIONS:
        for each_formatter_command in [
            ["ruff", "format", file_path],
            [sys.executable, "-m", "ruff", "format", file_path],
            ["black", file_path],
            [sys.executable, "-m", "black", file_path],
        ]:
            try:
                format_run = subprocess.run(each_formatter_command, capture_output=True, text=True, timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)
                if format_run.returncode == 0:
                    break
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                break
    elif suffix in JS_EXTENSIONS or suffix in JSON_EXTENSIONS:
        if not has_prettier_config(file_path):
            sys.exit(0)
        try:
            subprocess.run(
                ["npx", "--yes", "prettier", "--write", file_path],
                capture_output=True,
                text=True,
                timeout=JS_FORMAT_TIMEOUT_SECONDS,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
