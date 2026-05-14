"""Behavioral tests for ``post_audit_thread_constants``.

Exercises the public API the consuming script depends on: the audit body
skeleton markers must be non-empty strings, and ``template_path()`` must
resolve to the ``audit-reply-template.md`` file actually shipped in the
pr-loop directory.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import sys

THIS_FILE_DIRECTORY = Path(__file__).resolve().parent

sys.modules.pop("config", None)
if str(THIS_FILE_DIRECTORY.parent) not in sys.path:
    sys.path.insert(0, str(THIS_FILE_DIRECTORY.parent))

from config import post_audit_thread_constants as constants_module


class AuditBodySkeletonMarkerTests(unittest.TestCase):
    def test_open_marker_is_non_empty_html_comment(self) -> None:
        open_marker = constants_module.AUDIT_BODY_SKELETON_OPEN_MARKER
        self.assertTrue(open_marker.startswith("<!--"))
        self.assertTrue(open_marker.endswith("-->"))

    def test_close_marker_is_non_empty_html_comment(self) -> None:
        close_marker = constants_module.AUDIT_BODY_SKELETON_CLOSE_MARKER
        self.assertTrue(close_marker.startswith("<!--"))
        self.assertTrue(close_marker.endswith("-->"))

    def test_open_and_close_markers_differ(self) -> None:
        self.assertNotEqual(
            constants_module.AUDIT_BODY_SKELETON_OPEN_MARKER,
            constants_module.AUDIT_BODY_SKELETON_CLOSE_MARKER,
        )


class TemplatePathResolutionTests(unittest.TestCase):
    def test_template_path_resolves_to_existing_markdown_file(self) -> None:
        resolved_path = constants_module.template_path()
        self.assertTrue(resolved_path.is_file(), f"missing: {resolved_path}")
        self.assertEqual(resolved_path.suffix, ".md")

    def test_template_contains_skeleton_markers(self) -> None:
        resolved_path = constants_module.template_path()
        template_text = resolved_path.read_text(encoding="utf-8")
        self.assertIn(constants_module.AUDIT_BODY_SKELETON_OPEN_MARKER, template_text)
        self.assertIn(constants_module.AUDIT_BODY_SKELETON_CLOSE_MARKER, template_text)


if __name__ == "__main__":
    unittest.main()
