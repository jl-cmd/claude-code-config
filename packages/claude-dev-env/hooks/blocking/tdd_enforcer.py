#!/usr/bin/env python3
"""
BDD Automate-phase gate (production code touch).

Blocks writes to production source files when no matching test exists
or the matching test has not been modified within the configured
freshness window. Enforces "TDD IS NON-NEGOTIABLE" from CLAUDE.md.
"""
import ast
import json
import re
import sys
import time
from pathlib import Path


_hooks_root_path_string = str(Path(__file__).resolve().parent.parent)
if _hooks_root_path_string not in sys.path:
    sys.path.insert(0, _hooks_root_path_string)

from config.messages import USER_FACING_TDD_NOTICE

PRODUCTION_EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx'}
SKIP_PATTERNS = {
    'test_', '_test.', '.test.', 'tests/', '__tests__/',
    'conftest', 'fixture', 'mock', 'stub'
}
SKIP_EXTENSIONS = {'.md', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.txt'}
DOTCLAUDE_PATH_SEGMENTS = frozenset({".claude"})
