"""Tests for clearink.hook.reading."""

from __future__ import annotations

import unittest

from clearink.hook.reading import _looks_like_paper, track_task_events
from clearink.hook.hook import hook_context


class TestLooksLikePaper(unittest.TestCase):
    """Tests for _looks_like_paper."""

    def test_pdf_extension_returns_true(self):
        self.assertTrue(_looks_like_paper("/path/to/document.pdf"))

    def test_txt_extension_returns_true(self):
        self.assertTrue(_looks_like_paper("/path/to/document.txt"))

    def test_md_extension_returns_true(self):
        self.assertTrue(_looks_like_paper("/path/to/document.md"))

    def test_filename_contains_paper_returns_true(self):
        self.assertTrue(_looks_like_paper("/path/to/some_paper_notes.txt"))

    def test_filename_contains_arxiv_returns_true(self):
        self.assertTrue(_looks_like_paper("/path/to/arxiv_1234.pdf"))

    def test_filename_contains_article_returns_true(self):
        self.assertTrue(_looks_like_paper("/path/to/article_summary.md"))

    def test_py_extension_returns_false(self):
        self.assertFalse(_looks_like_paper("/path/to/script.py"))

    def test_random_filename_returns_false(self):
        self.assertFalse(_looks_like_paper("/path/to/random_file.xyz"))


class TestTrackTaskEvents(unittest.TestCase):
    """Tests for track_task_events."""

    def setUp(self):
        # Reset hook_context before each test
        hook_context.pop("last_rejected_task", None)
        hook_context.pop("last_reassigned_task", None)

    def test_rejected_event_sets_last_rejected_task(self):
        context = {
            "event": "rejected",
            "task_id": "42",
            "from_teammate": "alice",
            "reason": "incomplete",
            "hook_context": hook_context,
        }
        track_task_events(context)
        self.assertEqual(hook_context.get("last_rejected_task"), "42")

    def test_reassigned_event_sets_last_reassigned_task(self):
        context = {
            "event": "reassigned",
            "task_id": "7",
            "to_teammate": "bob",
            "hook_context": hook_context,
        }
        track_task_events(context)
        self.assertEqual(hook_context.get("last_reassigned_task"), "7")

    def test_unknown_event_does_nothing(self):
        context = {
            "event": "created",
            "task_id": "1",
            "hook_context": hook_context,
        }
        track_task_events(context)
        self.assertNotIn("last_rejected_task", hook_context)
        self.assertNotIn("last_reassigned_task", hook_context)
