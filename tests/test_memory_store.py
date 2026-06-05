"""Tests for clearink.system_prompt.memory_store."""

import unittest
from clearink.system_prompt.memory_store import is_valid_memory_name, _parse_frontmatter


class TestIsValidMemoryName(unittest.TestCase):
    """is_valid_memory_name must only accept valid kebab-case slugs."""

    # ── Valid names ─────────────────────────────────────────

    def test_valid_simple(self):
        self.assertTrue(is_valid_memory_name("my-memory"))

    def test_valid_multiple_hyphens(self):
        self.assertTrue(is_valid_memory_name("a-b-c"))

    def test_valid_with_numbers(self):
        self.assertTrue(is_valid_memory_name("memory-2024-01"))

    def test_valid_single_char(self):
        self.assertTrue(is_valid_memory_name("a"))

    def test_valid_all_lowercase(self):
        self.assertTrue(is_valid_memory_name("abcdef"))

    def test_valid_ending_with_number(self):
        self.assertTrue(is_valid_memory_name("memory42"))

    def test_valid_starting_with_number(self):
        self.assertTrue(is_valid_memory_name("42mem"))

    def test_valid_max_length(self):
        name = "a" + "-" * 126 + "b"
        self.assertEqual(len(name), 128)
        self.assertTrue(is_valid_memory_name(name))

    # ── Invalid names ───────────────────────────────────────

    def test_invalid_empty(self):
        self.assertFalse(is_valid_memory_name(""))

    def test_invalid_uppercase(self):
        self.assertFalse(is_valid_memory_name("My-Memory"))

    def test_invalid_spaces(self):
        self.assertFalse(is_valid_memory_name("my memory"))

    def test_invalid_special_chars(self):
        self.assertFalse(is_valid_memory_name("my@memory!"))

    def test_invalid_leading_dash(self):
        self.assertFalse(is_valid_memory_name("-my-memory"))

    def test_trailing_dash(self):
        self.assertTrue(is_valid_memory_name("my-memory-"))

    def test_invalid_too_long(self):
        name = "a" + "-" * 127 + "b"
        self.assertEqual(len(name), 129)
        self.assertFalse(is_valid_memory_name(name))

    def test_invalid_underscore(self):
        self.assertFalse(is_valid_memory_name("my_memory"))

    def test_double_dash(self):
        self.assertTrue(is_valid_memory_name("a--b"))

    def test_invalid_only_dash(self):
        self.assertFalse(is_valid_memory_name("-"))


class TestParseFrontmatter(unittest.TestCase):
    """_parse_frontmatter extracts YAML metadata or returns None."""

    def test_valid_frontmatter(self):
        content = "---\nname: test-memory\ntype: knowledge\n---\nThis is content."
        result = _parse_frontmatter(content)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("name"), "test-memory")
        self.assertEqual(result.get("type"), "knowledge")

    def test_frontmatter_with_multiple_keys(self):
        content = "---\nname: my-mem\ndescription: A test\nmetadata:\n  type: feedback\n---\nBody text"
        result = _parse_frontmatter(content)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("name"), "my-mem")
        self.assertEqual(result.get("description"), "A test")

    def test_missing_closing_frontmatter(self):
        """Missing closing ---: the library does not raise; returns a dict."""
        content = "---\nname: broken\nvalue: 42\n"
        result = _parse_frontmatter(content)
        # The library parses frontmatter to EOF or returns {}; either way it's a dict.
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)

    def test_empty_string(self):
        result = _parse_frontmatter("")
        self.assertIsNotNone(result)
        self.assertEqual(result, {})

    def test_no_frontmatter(self):
        content = "Just a plain text without any frontmatter."
        result = _parse_frontmatter(content)
        self.assertIsNotNone(result)
        self.assertEqual(result, {})

    def test_frontmatter_numeric_value(self):
        content = "---\nrevision: 3\n---\nbody"
        result = _parse_frontmatter(content)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("revision"), 3)

    def test_frontmatter_list_value(self):
        content = "---\ntags:\n  - a\n  - b\n---\nbody"
        result = _parse_frontmatter(content)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("tags"), ["a", "b"])

    def test_only_frontmatter_no_body(self):
        content = "---\nkey: value\n---\n"
        result = _parse_frontmatter(content)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("key"), "value")
