"""Tests for clearink.hook.reading."""

from __future__ import annotations

import unittest

from clearink.hook.reading import _looks_like_paper, _format_journal_entry


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


class TestFormatJournalEntry(unittest.TestCase):
    """Tests for _format_journal_entry."""

    def test_returns_string_with_turn_number(self):
        context = {
            "turns": 3,
            "hook_context": {
                "current_paper": {"name": "Attention Paper"},
                "citation_requested": True,
                "papers_accessed": [
                    {"path": "/p1.pdf", "name": "paper1", "access_count": 2}
                ],
            },
            "messages": [
                {"role": "user", "content": "What does this formula mean?"}
            ],
        }
        result = _format_journal_entry(context)
        self.assertIn("Turn 3", result)

    def test_contains_timestamp(self):
        context = {
            "turns": 1,
            "hook_context": {
                "current_paper": {"name": "Test"},
                "citation_requested": False,
                "papers_accessed": [],
            },
            "messages": [],
        }
        result = _format_journal_entry(context)
        self.assertIn("--", result)

    def test_contains_paper_name(self):
        context = {
            "turns": 2,
            "hook_context": {
                "current_paper": {"name": "Transformer"},
                "citation_requested": False,
                "papers_accessed": [],
            },
            "messages": [],
        }
        result = _format_journal_entry(context)
        self.assertIn("Transformer", result)

    def test_contains_citation_flag(self):
        context = {
            "turns": 4,
            "hook_context": {
                "current_paper": {"name": "Paper A"},
                "citation_requested": True,
                "papers_accessed": [],
            },
            "messages": [],
        }
        result = _format_journal_entry(context)
        self.assertIn("True", result)

    def test_contains_papers_accessed_count(self):
        context = {
            "turns": 5,
            "hook_context": {
                "current_paper": {"name": "Paper B"},
                "citation_requested": False,
                "papers_accessed": [
                    {"path": "/a.pdf"},
                    {"path": "/b.pdf"},
                    {"path": "/c.pdf"},
                ],
            },
            "messages": [],
        }
        result = _format_journal_entry(context)
        self.assertIn("3", result)
