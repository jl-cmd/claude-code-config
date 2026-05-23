"""Tests for ``check_tests_use_isolated_filesystem_paths``.

Pattern class: tests that call ``Path.home()``, ``os.path.expanduser('~')``,
``os.getenv('HOME'|'USERPROFILE'|'TMPDIR'|…)``, ``os.environ['HOME'|…]``, or
``tempfile.gettempdir()`` without taking a ``monkeypatch`` fixture leak across
the suite. Only ``monkeypatch`` suppresses the finding, because
``monkeypatch.setenv(...)`` actually intercepts the env reads the probes
depend on. ``tmp_path``, ``tmp_path_factory``, ``tmpdir``, and
``tmpdir_factory`` allocate a sandbox path but do not intercept env reads, so
their presence alone does not suppress the finding (see
``test_should_flag_path_home_when_only_tmp_path_fixture_present``). Cited
SYNTHESIS evidence: ccc#476 F16, F19, F28; pa#136 F11.
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


def test_should_flag_path_home_when_only_tmp_path_fixture_present() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(tmp_path) -> None:\n"
        "    home_dir = Path.home()\n"
        "    (tmp_path / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_flag_path_home_when_only_positional_only_tmp_path_present() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(tmp_path, /) -> None:\n"
        "    home_dir = Path.home()\n"
        "    (tmp_path / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_allow_path_home_in_test_with_positional_only_monkeypatch_fixture() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile(monkeypatch, /) -> None:\n"
        "    monkeypatch.setenv('HOME', '/tmp/fake')\n"
        "    home_dir = Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_ignore_path_home_inside_nested_helper_function() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_writes_dotfile() -> None:\n"
        "    def _nested_helper() -> Path:\n"
        "        return Path.home()\n"
        "    assert callable(_nested_helper)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_ignore_path_home_inside_nested_lambda() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_makes_lambda() -> None:\n"
        "    lookup_home = lambda: Path.home()\n"
        "    assert callable(lookup_home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_path_home_inside_nested_class_body() -> None:
    # A class-level statement directly in a nested class body runs at
    # class-creation time during the test, so a Path.home() initializer there
    # executes on the test's runtime path and must be flagged.
    source = (
        "from pathlib import Path\n"
        "def test_defines_inner_class() -> None:\n"
        "    class Inner:\n"
        "        root = Path.home()\n"
        "    assert Inner is not None\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_ignore_nested_test_named_function_pytest_does_not_collect() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_outer_caller(monkeypatch) -> None:\n"
        "    monkeypatch.setenv('HOME', '/tmp/fake')\n"
        "    def test_home_helper() -> None:\n"
        "        Path.home()\n"
        "    assert callable(test_home_helper)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_still_flag_path_home_at_top_level_when_nested_helper_also_probes() -> None:
    source = (
        "from pathlib import Path\n"
        "def test_top_level_probe_survives_nested_scope() -> None:\n"
        "    target = Path.home() / '.myapp'\n"
        "    def _nested_helper() -> Path:\n"
        "        return Path.home()\n"
        "    target.write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)
    assert len(issues) == 1


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


def test_should_flag_expandvars_referencing_home_env_var() -> None:
    source = (
        "import os\n"
        "def test_expands_home() -> None:\n"
        "    target = os.path.expandvars('$HOME/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expandvars" in each_issue for each_issue in issues)


def test_should_flag_expandvars_referencing_temp_env_var() -> None:
    source = (
        "import os\n"
        "def test_expands_temp() -> None:\n"
        "    target = os.path.expandvars('$TEMP/scratch')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expandvars" in each_issue for each_issue in issues)


def test_should_flag_expandvars_with_braced_home_reference() -> None:
    source = (
        "import os\n"
        "def test_expands_braced_home() -> None:\n"
        "    target = os.path.expandvars('${USERPROFILE}/Documents')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expandvars" in each_issue for each_issue in issues)


def test_should_not_flag_expandvars_referencing_unrelated_var() -> None:
    source = (
        "import os\n"
        "def test_expands_unrelated() -> None:\n"
        "    token = os.path.expandvars('$MY_APP_TOKEN')\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_bare_imported_expanduser() -> None:
    source = (
        "from os.path import expanduser\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_bare_imported_expanduser_under_alias() -> None:
    source = (
        "from os.path import expanduser as expand_home\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = expand_home('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_aliased_os_path_module_expanduser() -> None:
    source = (
        "import os.path as op\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = op.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_bare_imported_getenv_for_home() -> None:
    source = (
        "from os import getenv\n"
        "def test_resolves_home() -> None:\n"
        "    home = getenv('HOME')\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_not_flag_bare_imported_getenv_for_unrelated_var() -> None:
    source = (
        "from os import getenv\n"
        "def test_resolves_token() -> None:\n"
        "    token = getenv('MY_APP_TOKEN')\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_aliased_os_module_path_expanduser() -> None:
    source = (
        "import os as o\n"
        "def test_reads_dotfile() -> None:\n"
        "    target = o.path.expanduser('~/.config/x')\n"
        "    open(target).read()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_aliased_os_module_getenv_for_home() -> None:
    source = (
        "import os as o\n"
        "def test_resolves_home() -> None:\n"
        "    home = o.getenv('HOME')\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_not_flag_aliased_os_module_getenv_for_unrelated_var() -> None:
    source = (
        "import os as o\n"
        "def test_resolves_token() -> None:\n"
        "    token = o.getenv('MY_APP_TOKEN')\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_os_environ_via_local_binding() -> None:
    source = (
        "import os\n"
        "def test_resolves_home() -> None:\n"
        "    e = os.environ\n"
        "    home = e['HOME']\n"
        "    print(home)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("HOME" in each_issue for each_issue in issues)


def test_should_not_flag_os_environ_local_binding_for_unrelated_var() -> None:
    source = (
        "import os\n"
        "def test_resolves_token() -> None:\n"
        "    e = os.environ\n"
        "    token = e['MY_APP_TOKEN']\n"
        "    print(token)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_path_home_inside_nested_function_within_nested_class_method() -> None:
    source = (
        "from pathlib import Path\n"
        "class TestFoo:\n"
        "    def test_unsafe(self) -> None:\n"
        "        class HomePath:\n"
        "            def build(self) -> Path:\n"
        "                def _inner() -> Path:\n"
        "                    return Path.home()\n"
        "                return _inner()\n"
        "        h = HomePath()\n"
        "        assert h is not None\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)
    assert any("test_unsafe" in each_issue for each_issue in issues)


def test_should_flag_lambda_probe_inside_nested_class_method() -> None:
    source = (
        "from pathlib import Path\n"
        "class TestFoo:\n"
        "    def test_unsafe(self) -> None:\n"
        "        class HomePath:\n"
        "            def build(self):\n"
        "                return (lambda: Path.home())()\n"
        "        h = HomePath()\n"
        "        assert h is not None\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


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


def test_should_flag_aliased_path_home_probe() -> None:
    source = (
        "from pathlib import Path as P\n"
        "def test_writes_dotfile() -> None:\n"
        "    home_dir = P.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("home" in each_issue.lower() for each_issue in issues)


def test_should_flag_aliased_module_import_home_probe() -> None:
    source = (
        "import pathlib as pathlib_alias\n"
        "def test_writes_dotfile() -> None:\n"
        "    home_dir = pathlib_alias.Path.home()\n"
        "    (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("home" in each_issue.lower() for each_issue in issues)


def test_should_allow_aliased_path_home_with_monkeypatch_fixture() -> None:
    source = (
        "from pathlib import Path as P\n"
        "def test_writes_dotfile(monkeypatch) -> None:\n"
        "    monkeypatch.setenv('HOME', '/tmp/fake')\n"
        "    home_dir = P.home()\n"
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


def test_should_ignore_test_method_inside_non_test_prefixed_helper_class() -> None:
    # Helper classes (non-Test* prefix) are not collected by pytest under the
    # repo's `python_classes = Test*` setting, so methods on them must not
    # produce HOME/TMP isolation findings.
    source = (
        "from pathlib import Path\n"
        "class HelperFactory:\n"
        "    def test_makes_home_probe(self) -> Path:\n"
        "        return Path.home()\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_test_method_inside_test_prefixed_class() -> None:
    # Test*-prefixed classes ARE collected by pytest under the repo's
    # `python_classes = Test*` setting, so methods on them must still produce
    # HOME/TMP isolation findings.
    source = (
        "from pathlib import Path\n"
        "class TestHomeProbing:\n"
        "    def test_makes_home_probe(self) -> None:\n"
        "        home_dir = Path.home()\n"
        "        (home_dir / '.myapp').write_text('x')\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)


def test_should_flag_path_home_inside_nested_class_method_of_outer_test() -> None:
    # A class defined locally inside a test executes its method bodies as
    # part of the test's runtime path once an instance is constructed. The
    # walker must descend into nested-class methods so a Path.home() probe
    # in __init__ or any other method is attributed to the outer test.
    source = (
        "from pathlib import Path\n"
        "class TestFoo:\n"
        "    def test_unsafe(self) -> None:\n"
        "        class HomePath:\n"
        "            def __init__(self) -> None:\n"
        "                self.real_home = Path.home()\n"
        "        h = HomePath()\n"
        "        assert h is not None\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("Path.home" in each_issue for each_issue in issues)
    assert any("test_unsafe" in each_issue for each_issue in issues)


def test_should_ignore_path_home_inside_standalone_nested_helper_function() -> None:
    # A standalone nested function defined inside a test body is its own
    # callable scope — it carries its own isolation contract and is not
    # part of the test's direct execution path. Probes there must remain
    # unattributed to the outer test (preserves existing scope boundary).
    source = (
        "from pathlib import Path\n"
        "def test_outer() -> None:\n"
        "    def helper() -> Path:\n"
        "        return Path.home()\n"
        "    assert callable(helper)\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_flag_expanduser_with_tilde_only_argument() -> None:
    source = (
        "import os\n"
        "def test_reads_home() -> None:\n"
        "    target = os.path.expanduser('~')\n"
        "    assert target\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_flag_expanduser_with_named_user_tilde_argument() -> None:
    source = (
        "import os\n"
        "def test_reads_other_home() -> None:\n"
        "    target = os.path.expanduser('~alice/.config')\n"
        "    assert target\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert any("expanduser" in each_issue for each_issue in issues)


def test_should_not_flag_expanduser_with_relative_path_without_tilde() -> None:
    source = (
        "import os\n"
        "def test_resolves_relative() -> None:\n"
        "    target = os.path.expanduser('relative/path')\n"
        "    assert target\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []


def test_should_not_flag_expanduser_with_non_constant_argument() -> None:
    source = (
        "import os\n"
        "def test_resolves_dynamic(some_path) -> None:\n"
        "    target = os.path.expanduser(some_path)\n"
        "    assert target\n"
    )
    issues = check_tests_use_isolated_filesystem_paths(source, TEST_FILE_PATH)
    assert issues == []
