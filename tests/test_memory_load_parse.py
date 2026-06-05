"""Tests for clearink.system_prompt.memory_load parse helpers."""

import unittest
from clearink.system_prompt.memory_load import _parse_extracted_items, _normalize_memory_candidate


class TestParseExtractedItems(unittest.TestCase):
    """_parse_extracted_items parses structured text blocks separated by ---."""

    def test_single_item(self):
        text = (
            "---\n"
            "name: test-mem\n"
            "description: A test memory\n"
            "type: knowledge\n"
            "content: |\n"
            "  This is the content\n"
            "  with multiple lines\n"
            "---"
        )
        items = _parse_extracted_items(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "test-mem")
        self.assertEqual(items[0]["description"], "A test memory")
        self.assertEqual(items[0]["type"], "knowledge")
        self.assertEqual(items[0]["content"], "This is the content\nwith multiple lines")

    def test_multiple_items(self):
        text = (
            "---\n"
            "name: mem-one\n"
            "content: |\n"
            "  First content\n"
            "---\n"
            "---\n"
            "name: mem-two\n"
            "content: |\n"
            "  Second content\n"
            "---"
        )
        items = _parse_extracted_items(text)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "mem-one")
        self.assertEqual(items[1]["name"], "mem-two")

    def test_empty_input(self):
        self.assertEqual(_parse_extracted_items(""), [])

    def test_none_input(self):
        self.assertEqual(_parse_extracted_items("none"), [])

    def test_malformed_input_missing_name(self):
        text = (
            "---\n"
            "description: no name here\n"
            "content: |\n"
            "  some content\n"
            "---"
        )
        items = _parse_extracted_items(text)
        self.assertEqual(len(items), 0)

    def test_malformed_input_missing_content(self):
        text = (
            "---\n"
            "name: no-content\n"
            "description: missing content field\n"
            "type: knowledge\n"
            "---"
        )
        items = _parse_extracted_items(text)
        self.assertEqual(len(items), 0)

    def test_mixed_valid_and_invalid(self):
        text = (
            "---\n"
            "name: valid-item\n"
            "content: |\n"
            "  valid\n"
            "---\n"
            "---\n"
            "name: \n"
            "content: |\n"
            "  no name\n"
            "---"
        )
        items = _parse_extracted_items(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "valid-item")

    def test_content_with_block_scalar(self):
        text = (
            "---\n"
            "name: block-mem\n"
            "content: >\n"
            "  This is folded\n"
            "  content\n"
            "---"
        )
        items = _parse_extracted_items(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "block-mem")

    def test_item_with_all_fields(self):
        text = (
            "---\n"
            "name: full-mem\n"
            "description: Complete test\n"
            "type: user\n"
            "content: |\n"
            "  Full content here\n"
            "---"
        )
        items = _parse_extracted_items(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "full-mem")
        self.assertEqual(items[0]["description"], "Complete test")
        self.assertEqual(items[0]["type"], "user")
        self.assertEqual(items[0]["content"], "Full content here")


class TestNormalizeMemoryCandidate(unittest.TestCase):
    """_normalize_memory_candidate extracts a valid memory name from a line."""

    def test_simple_name(self):
        self.assertEqual(_normalize_memory_candidate("my-memory"), "my-memory")

    def test_strips_whitespace(self):
        self.assertEqual(_normalize_memory_candidate("  my-memory  "), "my-memory")

    def test_strips_markdown_list_prefix(self):
        self.assertEqual(_normalize_memory_candidate("- my-memory"), "my-memory")

    def test_extracts_bracketed_name(self):
        self.assertEqual(
            _normalize_memory_candidate("some text [my-mem] more text"),
            "my-mem",
        )

    def test_strips_md_extension(self):
        self.assertEqual(_normalize_memory_candidate("my-memory.md"), "my-memory")

    def test_takes_first_word(self):
        self.assertEqual(
            _normalize_memory_candidate("my-memory other words"),
            "my-memory",
        )

    def test_empty_input(self):
        self.assertEqual(_normalize_memory_candidate(""), "")

    def test_none_text(self):
        self.assertEqual(_normalize_memory_candidate("none"), "")

    def test_none_mixed_case(self):
        self.assertEqual(_normalize_memory_candidate("None"), "")

    def test_invalid_name_returns_empty(self):
        self.assertEqual(_normalize_memory_candidate("INVALID"), "")

    def test_name_with_spaces_takes_first_word(self):
        self.assertEqual(_normalize_memory_candidate("my memory"), "my")

    def test_markdown_link_with_hyphens(self):
        self.assertEqual(
            _normalize_memory_candidate("[my-long-memory-name]"),
            "my-long-memory-name",
        )

    def test_bracketed_name_wins_over_text(self):
        """When brackets are present, their content is used over the raw text."""
        self.assertEqual(
            _normalize_memory_candidate("garbage [real-name] trailing"),
            "real-name",
        )

    def test_dash_prefix_stripped_fully(self):
        self.assertEqual(
            _normalize_memory_candidate("- - my-memory"),
            "my-memory",
        )

    def test_markdown_link_with_dash_prefix(self):
        self.assertEqual(
            _normalize_memory_candidate("- [mem-name]"),
            "mem-name",
        )
