"""Coherence tests for groq_bugteam_spec module import surface.

The behavioral contract for apply_fix_from_spec lives in
test_groq_bugteam_apply_fix_from_spec.py; those tests pass whether the
function is defined in groq_bugteam.py directly or re-exported from the
spec module. This file exists solely so the spec module has a
same-named test companion for filename-based test pairing.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys


def _load_spec_module():
    scripts_directory = pathlib.Path(__file__).parent
    sys.path.insert(0, str(scripts_directory))
    for cached_module_name in list(sys.modules):
        if cached_module_name == "config" or cached_module_name.startswith("config."):
            del sys.modules[cached_module_name]
    module_path = scripts_directory / "groq_bugteam_spec.py"
    module_spec = importlib.util.spec_from_file_location(
        "groq_bugteam_spec", module_path
    )
    loaded_module = importlib.util.module_from_spec(module_spec)
    sys.modules["groq_bugteam_spec"] = loaded_module
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


groq_bugteam_spec = _load_spec_module()


def test_apply_fix_from_spec_is_callable():
    assert callable(groq_bugteam_spec.apply_fix_from_spec)


def test_run_spec_mode_main_is_callable():
    assert callable(groq_bugteam_spec.run_spec_mode_main)


def test_is_spec_mode_invocation_detects_flag_value_pair():
    assert groq_bugteam_spec.is_spec_mode_invocation(["--mode", "spec"]) is True
    assert groq_bugteam_spec.is_spec_mode_invocation(["--mode", "pipeline"]) is False
    assert groq_bugteam_spec.is_spec_mode_invocation([]) is False
