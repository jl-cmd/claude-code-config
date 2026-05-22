"""Tests for ``check_tests_use_isolated_filesystem_paths``.

Pattern class: tests that call ``Path.home()``, ``os.path.expanduser('~')``,
``os.getenv('HOME'|'USERPROFILE'|'TMPDIR'|…)``, ``os.environ['HOME'|…]``, or
``tempfile.gettempdir()`` without taking a pytest isolation fixture
(``tmp_path``, ``tmp_path_factory``, ``tmpdir``, ``tmpdir_factory``,
``monkeypatch``) leak across the suite. Cited SYNTHESIS evidence: ccc#476
F16, F19, F28; pa#136 F11.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIR / "code_rules_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
check_tests_use_isolated_filesystem_paths = hook_module.check_tests_use_isolated_filesystem_paths

TEST_FILE_PATH = "/project/src/test_module.py"
PRODUCTION_FILE_PATH = "/project/src/module.py"


def test_should_flag_path_home_in_test_without_fixture() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile() -> None:\n"
        "    home_dir = Path.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_allow_path_home_in_test_with_tmp_path_fixture() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(tmp_path) -> None:\n"
        "    home_dir = Path.home()\n"
        "    (tmp_path / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_allow_path_home_in_test_with_positional_only_fixture() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(tmp_path, /) -> None:\n"
        "    home_dir = Path.home()\n"
        "    (tmp_path / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_ignore_path_home_inside_nested_helper_function() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(tmp_path) -> None:\n"
        "    def _nested_helper() -> Path:\n"
        "        return Path.home()\n"
        "    target = tmp_path / '.myapp'\n"
        "    target.write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_ignore_path_home_inside_nested_lambda() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_makes_lambda(tmp_path) -> None:\n"
        "    lookup_home = lambda: Path.home()\n"
        "    (tmp_path / 'x').write_text('y')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_ignore_path_home_inside_nested_class_body() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_defines_inner_class(tmp_path) -> None:\n"
        "    class Inner:\n"
        "        root = Path.home()\n"
        "    (tmp_path / 'x').write_text('y')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_allow_path_home_in_test_with_monkeypatch_fixture() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(monkeypatch, tmp_path) -> None:\n"
        "    monkeypatch.setenv('HOME', str(tmp_path))\n"
        "    home_dir = Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_expanduser_call_without_isolation() -> None:
    source = (
        "import os\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = os.path.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_tempfile_gettempdir_without_isolation() -> None:
    source = (
        "import tempfile\n"
        "def test_writes_to_shared_temp() -> None:\n"
        "    base = tempfile.gettempdir()\n"
        "    (base + '/x.txt')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("gettempdir" in each_issue for each_issue in issues)


def test_should_flag_os_environ_subscript_for_home() -> None:
    source = (
        "import os\n"
        "def test_resolves_home() -> None:\n"
        "    home = os.environ['HOME']\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_flag_os_environ_subscript_for_userprofile() -> None:
    source = (
        "import os\n"
        "def test_resolves_userprofile() -> None:\n"
        "    user = os.environ['USERPROFILE']\n"
        "    print(user)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("USERPROFILE" in each_issue for each_issue in issues)


def test_should_flag_os_getenv_for_tmpdir() -> None:
    source = (
        "import os\n"
        "def test_resolves_tmpdir() -> None:\n"
        "    tmp_root = os.getenv('TMPDIR')\n"
        "    print(tmp_root)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("TMPDIR" in each_issue for each_issue in issues)


def test_should_not_flag_os_getenv_for_unrelated_var() -> None:
    source = (
        "import os\n"
        "def test_unrelated_env() -> None:\n"
        "    value = os.getenv('MY_APP_TOKEN')\n"
        "    print(value)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_not_run_on_production_files() -> None:
    source = (
        "from pathlib import Path\ndef test_writes_dotfile() -> None:\n    home_dir = Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_ignore_module_level_helpers_in_test_files() -> None:
    source = (
        "from pathlib import Path\n"
        "def helper_paths() -> Path:\n"
        "    return Path.home()\n"
        "def test_uses_helper(tmp_path) -> None:\n"
        "    helper_paths()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_ignore_helper_named_with_bare_test_prefix() -> None:
    source = (
        "from pathlib import Path\n"
        "def testing_factory() -> Path:\n"
        "    return Path.home()\n"
        "def testify_connection() -> Path:\n"
        "    return Path.home()\n"
        "def testament_root() -> Path:\n"
        "    return Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_handle_async_test_functions() -> None:
    source = (
        "from pathlib import Path\n"
        "async def test_writes_dotfile() -> None:\n"
        "    home_dir = Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_recognize_should_prefix_functions_as_tests() -> None:
    source = (
        "from pathlib import Path\n"
        "def should_write_dotfile() -> None:\n"
        "    home_dir = Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_skip_when_source_fails_to_parse() -> None:
    source = "def test_broken(:\n"
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_cap_issue_count_at_configured_maximum() -> None:
    repeated_probes = "\n".join(f"    p{each_index} = Path.home()" for each_index in range(20))
    source = f"from pathlib import Path\ndef test_many_probes() -> None:\n{repeated_probes}\n"
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert len(issues) == hook_module.MAX_TEST_ISOLATION_ISSUES
