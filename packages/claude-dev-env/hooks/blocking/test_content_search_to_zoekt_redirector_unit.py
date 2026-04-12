import importlib.util
import pathlib
import unittest
from typing import Any

HOOK_PATH = pathlib.Path(__file__).parent / "content-search-to-zoekt-redirector.py"
_spec = importlib.util.spec_from_file_location("zoekt_redirector_hook", HOOK_PATH)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


class BuildBlockPayloadTests(unittest.TestCase):
    def test_payload_matches_contract(self) -> None:
        payload: dict[str, Any] = _module.build_block_payload("demo", "body")
        self.assertTrue(payload["systemMessage"].startswith("[destructive-gate] "))
        self.assertEqual(payload["reason"], "body")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(payload["suppressOutput"], True)


if __name__ == "__main__":
    unittest.main()
