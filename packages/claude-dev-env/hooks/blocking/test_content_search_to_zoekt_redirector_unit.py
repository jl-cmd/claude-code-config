import pathlib
import sys
import unittest
from typing import Any

HOOK_DIRECTORY = pathlib.Path(__file__).resolve().parent
if str(HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(HOOK_DIRECTORY))

from content_search_zoekt_block_payload import DESTRUCTIVE_GATE_LABEL_PREFIX, build_block_payload


class BuildBlockPayloadTests(unittest.TestCase):
    def test_payload_matches_contract(self) -> None:
        payload: dict[str, Any] = build_block_payload("demo", "body")
        prefix_with_space = f"{DESTRUCTIVE_GATE_LABEL_PREFIX} "
        self.assertTrue(payload["systemMessage"].startswith(prefix_with_space))
        self.assertEqual(payload["reason"], "body")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(payload["suppressOutput"], True)


if __name__ == "__main__":
    unittest.main()
