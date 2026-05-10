"""Tests for md_to_html_companion hook."""

import json
import os
import subprocess
import sys
import tempfile


HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "md_to_html_companion.py")


class _RunHook:
    def __call__(self, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )


_run_hook = _RunHook()


def _write_md_and_run(file_path: str, content: str):
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    result = _run_hook("Write", {"file_path": file_path, "content": content})
    return result


def test_generates_html_companion():
    with tempfile.TemporaryDirectory() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        html_path = os.path.join(tmp, "guide.html")

        os.makedirs(tmp, exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Hello\n\nThis is a test.")

        result = _run_hook(
            "Write", {"file_path": md_path, "content": "# Hello\n\nThis is a test."}
        )
        assert result.returncode == 0
        assert os.path.exists(html_path)


def test_html_contains_heading():
    with tempfile.TemporaryDirectory() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Hello World")

        _run_hook("Write", {"file_path": md_path, "content": "# Hello World"})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<h1>" in html
        assert "Hello World" in html


def test_html_wraps_in_template():
    with tempfile.TemporaryDirectory() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("plain text")

        _run_hook("Write", {"file_path": md_path, "content": "plain text"})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<!DOCTYPE html>" in html
        assert "<style>" in html


def test_skips_non_md_files():
    with tempfile.TemporaryDirectory() as tmp:
        py_path = os.path.join(tmp, "main.py")
        html_path = os.path.join(tmp, "main.html")

        os.makedirs(tmp, exist_ok=True)
        with open(py_path, "w", encoding="utf-8") as f:
            f.write("x = 1")

        result = _run_hook("Write", {"file_path": py_path, "content": "x = 1"})
        assert result.returncode == 0
        assert not os.path.exists(html_path)


def test_skips_claude_dir():
    with tempfile.TemporaryDirectory() as tmp:
        claude_dir = os.path.join(tmp, ".claude")
        md_path = os.path.join(claude_dir, "CLAUDE.md")
        html_path = os.path.join(claude_dir, "CLAUDE.html")

        os.makedirs(claude_dir, exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# CLAUDE.md")

        result = _run_hook("Write", {"file_path": md_path, "content": "# CLAUDE.md"})
        assert result.returncode == 0
        assert not os.path.exists(html_path)


def test_unknown_tool_passes():
    result = _run_hook("Grep", {"pattern": "foo"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_empty_file_path_passes():
    result = _run_hook("Write", {"file_path": "", "content": "# Hello"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_nonexistent_md_passes():
    result = _run_hook(
        "Write",
        {"file_path": "/nonexistent/path/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0


def test_converts_code_fence():
    with tempfile.TemporaryDirectory() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("```python\nprint('hi')\n```")

        _run_hook(
            "Write", {"file_path": md_path, "content": "```python\nprint('hi')\n```"}
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<pre>" in html
        assert "<code" in html
        assert "print('hi')" in html


def test_converts_bold():
    with tempfile.TemporaryDirectory() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("This is **bold** text.")

        _run_hook("Write", {"file_path": md_path, "content": "This is **bold** text."})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<strong>bold</strong>" in html
