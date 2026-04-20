"""Adds .github/scripts to sys.path so sync_ai_rules is importable in tests.

The hook-local ``config`` module collision with the repo-root ``config/``
package is handled by the root ``conftest.py`` via ``pytest_collectstart``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))
