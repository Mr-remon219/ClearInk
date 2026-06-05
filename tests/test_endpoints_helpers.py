import unittest
from unittest.mock import patch

from clearink.api.endpoints import (
    _extract_response,
    _ok,
    _err,
    _make_user_message,
)


class TestExtractResponse(unittest.TestCase):
    def test_last_assistant_text(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "first answer"},
            {"role": "user", "content": "follow up"},
            {"role": "assistant", "content": "second answer"},
        ]
        result = _extract_response(messages)
        self.assertEqual(result, "second answer")

    def test_skips_non_assistant_roles(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "system", "content": "you are a bot"},
        ]
        result = _extract_response(messages)
        self.assertIsNone(result)

    def test_skips_empty_text(self):
        messages = [
            {"role": "assistant", "content": ""},
            {"role": "assistant", "content": "   "},
        ]
        result = _extract_response(messages)
        self.assertIsNone(result)

    def test_returns_none_for_empty_list(self):
        self.assertIsNone(_extract_response([]))

    def test_returns_first_assistant_if_no_later(self):
        messages = [
            {"role": "assistant", "content": "first"},
            {"role": "user", "content": "next"},
        ]
        result = _extract_response(messages)
        self.assertEqual(result, "first")

    def test_returns_most_recent_assistant_only(self):
        messages = [
            {"role": "assistant", "content": "earlier"},
            {"role": "assistant", "content": "later"},
        ]
        result = _extract_response(messages)
        self.assertEqual(result, "later")

    def test_handles_content_with_whitespace(self):
        messages = [
            {"role": "assistant", "content": "  valid text  "},
        ]
        result = _extract_response(messages)
        self.assertEqual(result, "valid text")

    def test_skips_only_whitespace_then_finds_valid(self):
        messages = [
            {"role": "assistant", "content": "   "},
            {"role": "assistant", "content": "actual answer"},
        ]
        result = _extract_response(messages)
        self.assertEqual(result, "actual answer")

    def test_single_message_list(self):
        messages = [{"role": "assistant", "content": "only answer"}]
        result = _extract_response(messages)
        self.assertEqual(result, "only answer")

    def test_no_assistant_at_all(self):
        messages = [
            {"role": "user", "content": "q1"},
            {"role": "user", "content": "q2"},
        ]
        result = _extract_response(messages)
        self.assertIsNone(result)


class TestOk(unittest.TestCase):
    def test_returns_ok_true(self):
        result = _ok()
        self.assertEqual(result, {"ok": True})

    def test_includes_extra_kwargs(self):
        result = _ok(session_id="abc", mode=1)
        self.assertEqual(result, {"ok": True, "session_id": "abc", "mode": 1})

    def test_overrides_not_possible(self):
        result = _ok(**{"ok": False})
        self.assertEqual(result, {"ok": True})

    def test_with_only_one_kwarg(self):
        result = _ok(count=42)
        self.assertEqual(result, {"ok": True, "count": 42})

    def test_empty_kwargs_still_ok(self):
        result = _ok()
        self.assertIn("ok", result)
        self.assertTrue(result["ok"])


class TestErr(unittest.TestCase):
    def test_returns_ok_false_with_message(self):
        result = _err("something went wrong")
        self.assertEqual(result, {"ok": False, "error": "something went wrong"})

    def test_message_is_required(self):
        result = _err("")
        self.assertEqual(result, {"ok": False, "error": ""})

    def test_special_characters_in_message(self):
        msg = "error: code 500! <internal>"
        result = _err(msg)
        self.assertEqual(result, {"ok": False, "error": msg})

    def test_unicode_in_error(self):
        result = _err("输入错误")
        self.assertEqual(result, {"ok": False, "error": "输入错误"})

    def test_only_contains_ok_and_error(self):
        result = _err("fail")
        self.assertEqual(set(result.keys()), {"ok", "error"})


class TestMakeUserMessage(unittest.TestCase):
    def test_wraps_text_with_mode_prefix(self):
        with patch("clearink.api.endpoints.mode_mod") as mock_mode:
            mock_mode.get_mode_prompt.return_value = "Analyze formulae."
            result = _make_user_message("what is eq(5)?", current_mode=1)
        self.assertEqual(result["role"], "user")
        self.assertIn("what is eq(5)?", result["content"])
        self.assertIn("[Mode 1 instructions begin]", result["content"])
        self.assertIn("Analyze formulae.", result["content"])
        self.assertIn("[Mode 1 instructions end]", result["content"])

    def test_with_mode_2(self):
        with patch("clearink.api.endpoints.mode_mod") as mock_mode:
            mock_mode.get_mode_prompt.return_value = "Answer paper Q&A."
            result = _make_user_message("what is this about?", current_mode=2)
        self.assertEqual(result["role"], "user")
        self.assertIn("[Mode 2 instructions begin]", result["content"])
        self.assertIn("Answer paper Q&A.", result["content"])
        self.assertIn("what is this about?", result["content"])

    def test_no_mode_prompt(self):
        with patch("clearink.api.endpoints.mode_mod") as mock_mode:
            mock_mode.get_mode_prompt.return_value = ""
            result = _make_user_message("just text", current_mode=1)
        self.assertEqual(result, {"role": "user", "content": "just text"})

    def test_includes_original_text_at_end(self):
        with patch("clearink.api.endpoints.mode_mod") as mock_mode:
            mock_mode.get_mode_prompt.return_value = "prefix."
            result = _make_user_message("my question", current_mode=1)
        self.assertTrue(result["content"].endswith("my question"))

    def test_text_with_newlines(self):
        with patch("clearink.api.endpoints.mode_mod") as mock_mode:
            mock_mode.get_mode_prompt.return_value = "prompt."
            result = _make_user_message("line1\nline2", current_mode=2)
        self.assertIn("line1\nline2", result["content"])

    def test_empty_text_with_prefix(self):
        with patch("clearink.api.endpoints.mode_mod") as mock_mode:
            mock_mode.get_mode_prompt.return_value = "prompt."
            result = _make_user_message("", current_mode=1)
        self.assertIn("[Mode 1 instructions end]", result["content"])
