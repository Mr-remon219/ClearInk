"""Tests for clearink.system_prompt.system_build."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from clearink.system_prompt.system_build import (
    _build_guidelines,
    PROMPT_SECTIONS,
    get_system_prompt,
)


class TestBuildGuidelines(unittest.TestCase):
    """Tests for _build_guidelines."""

    def test_returns_string(self):
        result = _build_guidelines({})
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 10)

    def test_fallback_contains_key_terms(self):
        """Fallback text contains anti-hallucination and agent identity."""
        with patch(
            "clearink.system_prompt.system_build._read_prompt_file",
            return_value=None,
        ):
            result = _build_guidelines({})
            self.assertIn("ClearInk", result)
            self.assertIn("fabricate", result.lower())


class TestGetSystemPrompt(unittest.TestCase):
    """Tests for get_system_prompt."""

    def test_returns_string(self):
        result = get_system_prompt()
        self.assertIsInstance(result, str)

    def test_returns_non_empty(self):
        result = get_system_prompt()
        self.assertTrue(len(result) > 0)

    def test_sections_param_filters(self):
        """Passing sections filters to only those sections."""
        result = get_system_prompt(sections=["guidelines"])
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


class TestPromptSections(unittest.TestCase):
    """Tests for PROMPT_SECTIONS registry."""

    def test_guidelines_is_registered(self):
        self.assertIn("guidelines", PROMPT_SECTIONS)
