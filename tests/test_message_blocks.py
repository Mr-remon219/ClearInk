from __future__ import annotations

import unittest
from types import SimpleNamespace
from collections.abc import Mapping

from clearink.message.blocks import (
    content_block_to_dict,
    extract_text_from_content,
    sanitize_messages_for_no_thinking,
    _is_thinking_block,
)


class TestExtractTextFromContent(unittest.TestCase):
    """Test extraction of visible text from various content formats."""

    def test_string_returns_self(self) -> None:
        result = extract_text_from_content("hello world")
        self.assertEqual(result, "hello world")

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(extract_text_from_content(""), "")

    def test_list_with_text_blocks(self) -> None:
        content = [
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "world"},
        ]
        self.assertEqual(extract_text_from_content(content), "Hello world")

    def test_skips_thinking_block(self) -> None:
        content = [
            {"type": "text", "text": "Visible"},
            {"type": "thinking", "thinking": "hidden"},
        ]
        self.assertEqual(extract_text_from_content(content), "Visible")

    def test_skips_redacted_thinking_block(self) -> None:
        content = [
            {"type": "text", "text": "Result"},
            {"type": "redacted_thinking", "data": "..."},
        ]
        self.assertEqual(extract_text_from_content(content), "Result")

    def test_skips_tool_use_block(self) -> None:
        content = [
            {"type": "text", "text": "Using tool..."},
            {"type": "tool_use", "name": "search", "input": {"q": "test"}},
        ]
        self.assertEqual(extract_text_from_content(content), "Using tool...")

    def test_skips_tool_result_block(self) -> None:
        content = [
            {"type": "text", "text": "Final answer"},
            {"type": "tool_result", "content": "some result"},
        ]
        self.assertEqual(extract_text_from_content(content), "Final answer")

    def test_empty_list_returns_empty(self) -> None:
        self.assertEqual(extract_text_from_content([]), "")

    def test_no_text_blocks_returns_empty(self) -> None:
        content = [
            {"type": "thinking", "thinking": "hidden"},
            {"type": "tool_use", "name": "search", "input": {}},
        ]
        self.assertEqual(extract_text_from_content(content), "")

    def test_non_text_list_returns_empty(self) -> None:
        self.assertEqual(extract_text_from_content(42), "")
        self.assertEqual(extract_text_from_content(None), "")
        self.assertEqual(extract_text_from_content(object()), "")

    def test_handles_text_with_missing_text_key(self) -> None:
        content = [{"type": "text"}]
        self.assertEqual(extract_text_from_content(content), "")

    def test_handles_text_with_none_text_value(self) -> None:
        content = [{"type": "text", "text": None}]
        self.assertEqual(extract_text_from_content(content), "")


class TestSanitizeMessagesForNoThinking(unittest.TestCase):
    """Test removal of thinking blocks from messages."""

    def test_removes_thinking_blocks(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "deep thoughts"},
                    {"type": "text", "text": "Answer here"},
                ],
            }
        ]
        sanitized = sanitize_messages_for_no_thinking(messages)
        content = sanitized[0]["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["type"], "text")

    def test_removes_redacted_thinking_blocks(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "redacted_thinking", "data": "redacted"},
                    {"type": "text", "text": "Visible text"},
                ],
            }
        ]
        sanitized = sanitize_messages_for_no_thinking(messages)
        content = sanitized[0]["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["type"], "text")

    def test_does_not_mutate_original_messages(self) -> None:
        original = [
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "secret"},
                    {"type": "text", "text": "public"},
                ],
            }
        ]
        sanitized = sanitize_messages_for_no_thinking(original)
        self.assertNotEqual(id(original), id(sanitized))

        # Verify original is untouched
        self.assertEqual(len(original[0]["content"]), 2)

    def test_handles_string_content(self) -> None:
        messages = [{"role": "user", "content": "plain text"}]
        sanitized = sanitize_messages_for_no_thinking(messages)
        self.assertEqual(sanitized[0]["content"], "plain text")

    def test_handles_empty_content_list(self) -> None:
        messages = [{"role": "user", "content": []}]
        sanitized = sanitize_messages_for_no_thinking(messages)
        self.assertEqual(sanitized[0]["content"], "")

    def test_only_thinking_blocks_drops_message(self) -> None:
        """Assistant messages with only thinking blocks are dropped entirely."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "only thinking"}
                ],
            }
        ]
        sanitized = sanitize_messages_for_no_thinking(messages)
        self.assertEqual(sanitized, [])

    def test_only_thinking_blocks_user_yields_empty(self) -> None:
        """User messages with only thinking blocks get empty content string."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "thinking", "thinking": "only thinking"}
                ],
            }
        ]
        sanitized = sanitize_messages_for_no_thinking(messages)
        self.assertEqual(sanitized[0]["content"], "")

    def test_preserves_non_content_fields(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "hello"}],
                "extra_field": "preserved",
            }
        ]
        sanitized = sanitize_messages_for_no_thinking(messages)
        self.assertEqual(sanitized[0]["extra_field"], "preserved")


class TestIsThinkingBlock(unittest.TestCase):
    """Test _is_thinking_block predicate."""

    def test_thinking_type_returns_true(self) -> None:
        self.assertTrue(_is_thinking_block({"type": "thinking"}))

    def test_redacted_thinking_type_returns_true(self) -> None:
        self.assertTrue(_is_thinking_block({"type": "redacted_thinking"}))

    def test_text_type_returns_false(self) -> None:
        self.assertFalse(_is_thinking_block({"type": "text"}))

    def test_tool_use_type_returns_false(self) -> None:
        self.assertFalse(_is_thinking_block({"type": "tool_use"}))

    def test_unknown_type_returns_false(self) -> None:
        self.assertFalse(_is_thinking_block({"type": "image"}))

    def test_empty_dict_returns_false(self) -> None:
        self.assertFalse(_is_thinking_block({}))

    def test_block_with_thinking_key_is_thinking(self) -> None:
        """A block with a 'thinking' key is also considered a thinking block."""
        self.assertTrue(_is_thinking_block({"type": "text", "thinking": "secret"}))


class TestContentBlockToDict(unittest.TestCase):
    """Test content_block_to_dict with various block formats."""

    def test_mapping_protocol_dict(self) -> None:
        """A plain dict (Mapping) is converted directly."""
        block = {"type": "text", "text": "hello"}
        result = content_block_to_dict(block)
        self.assertEqual(result, {"type": "text", "text": "hello"})

    def test_mapping_protocol_custom(self) -> None:
        """A custom Mapping object is converted via dict()."""

        class CustomMapping(Mapping):
            def __getitem__(self, key: str) -> str:
                return {"type": "text", "text": "mapped"}[key]

            def __iter__(self):
                return iter(["type", "text"])

            def __len__(self) -> int:
                return 2

        result = content_block_to_dict(CustomMapping())
        self.assertEqual(result["type"], "text")
        self.assertEqual(result["text"], "mapped")

    def test_to_dict_method(self) -> None:
        """An object with a to_dict() method is used."""
        block = SimpleNamespace(to_dict=lambda: {"type": "text", "text": "from_to_dict"})
        result = content_block_to_dict(block)
        self.assertEqual(result["type"], "text")
        self.assertEqual(result["text"], "from_to_dict")

    def test_field_reflection(self) -> None:
        """An object without Mapping or to_dict falls back to field reflection."""
        block = SimpleNamespace(type="tool_use", name="search", input={"q": "test"}, id="123")
        result = content_block_to_dict(block)
        self.assertEqual(result["type"], "tool_use")
        self.assertEqual(result["name"], "search")
        self.assertEqual(result["id"], "123")
        self.assertEqual(result["input"], {"q": "test"})

    def test_fallback_to_str(self) -> None:
        """An object with no recognized fields is converted to a fallback dict."""
        block = SimpleNamespace()
        result = content_block_to_dict(block)
        # fallback: type from block.type or class name
        self.assertIn("type", result)
        self.assertIn("text", result)

    def test_none_block(self) -> None:
        """None is not a Mapping, has no to_dict, and has no fields."""
        result = content_block_to_dict(None)
        self.assertIn("type", result)
        self.assertIn("text", result)

    def test_field_reflection_thinking_block(self) -> None:
        """A thinking block via SimpleNamespace is correctly serialized."""
        block = SimpleNamespace(
            type="thinking", thinking="I am thinking...", signature="sig123"
        )
        result = content_block_to_dict(block)
        self.assertEqual(result["type"], "thinking")
        self.assertEqual(result["thinking"], "I am thinking...")
        self.assertEqual(result["signature"], "sig123")


if __name__ == "__main__":
    unittest.main()
