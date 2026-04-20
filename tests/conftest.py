"""Adds .github/scripts to sys.path so sync_ai_rules is importable in tests.

Also evicts the hook-local flat ``config`` module from ``sys.modules`` if a
prior test collection (``packages/claude-dev-env/hooks/git-hooks/``) cached it;
that cache otherwise shadows the repo-root ``config/`` package and breaks
``from config.sync_ai_rules_paths import ...`` during collection.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))
sys.modules.pop("config", None)
