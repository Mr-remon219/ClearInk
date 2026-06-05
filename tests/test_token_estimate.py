import unittest

from clearink.context_compact.token_estimate import (
    count_total_chars,
    estimate_tokens,
)


class TestCountTotalChars(unittest.TestCase):
    def test_empty_list_returns_zero(self):
        self.assertEqual(count_total_chars([]), 0)

    def test_sums_string_content(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        self.assertEqual(count_total_chars(messages), 10)

    def test_handles_nested_list_of_content_blocks(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Hello, "},
                    {"type": "text", "text": "world!"},
                ],
            },
        ]
        # "Hello, " = 7, "world!" = 6, total = 13
        self.assertEqual(count_total_chars(messages), 13)

    def test_handles_mixed_string_and_block_content(self):
        messages = [
            {"role": "user", "content": "question"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "detailed "},
                    {"type": "text", "text": "answer"},
                ],
            },
        ]
        # "question" = 8, "detailed " = 9, "answer" = 6, total = 23
        self.assertEqual(count_total_chars(messages), 23)

    def test_skips_non_dict_messages(self):
        messages = ["not a dict", {"role": "user", "content": "valid"}]
        self.assertEqual(count_total_chars(messages), 5)

    def test_handles_missing_content_key(self):
        messages = [{"role": "user"}]  # no 'content' key
        self.assertEqual(count_total_chars(messages), 0)

    def test_handles_none_content(self):
        messages = [{"role": "user", "content": None}]
        self.assertEqual(count_total_chars(messages), 0)

    def test_handles_non_string_in_block(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "tool_result", "content": 123},
                ],
            },
        ]
        # 123 is not a string, should be treated as "" per .get fallback
        # text="hello" = 5, content=123 doesn't match isinstance check
        self.assertEqual(count_total_chars(messages), 5)

    def test_handles_blocks_using_content_key(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_result", "content": "via content key"},
                ],
            },
        ]
        self.assertEqual(count_total_chars(messages), 15)

    def test_empty_string_in_content(self):
        messages = [{"role": "user", "content": ""}]
        self.assertEqual(count_total_chars(messages), 0)

    def test_empty_list_in_content(self):
        messages = [{"role": "assistant", "content": []}]
        self.assertEqual(count_total_chars(messages), 0)

    def test_multiple_messages_with_blocks(self):
        messages = [
            {"role": "user", "content": "start"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "block1 "},
                    {"type": "text", "text": "block2 "},
                    {"type": "thinking", "thinking": "hidden"},
                ],
            },
            {"role": "user", "content": "end"},
        ]
        # "start" = 5, "block1 " = 7, "block2 " = 7, "end" = 3
        # "hidden" is under "thinking" key, not "text" or "content"
        self.assertEqual(count_total_chars(messages), 22)

    def test_content_with_unicode(self):
        messages = [
            {"role": "user", "content": "你好世界"},
        ]
        self.assertEqual(count_total_chars(messages), 4)

    def test_content_with_newlines_and_spaces(self):
        messages = [
            {"role": "user", "content": "line1\nline2\nline3"},
        ]
        self.assertEqual(count_total_chars(messages), 17)

    def test_block_with_text_preferred_over_content(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "text_field", "content": "content_field"},
                ],
            },
        ]
        # text is checked first, so "text_field" = 10
        self.assertEqual(count_total_chars(messages), 10)

    def test_large_number_of_messages(self):
        messages = [{"role": "user", "content": "x" * 100} for _ in range(100)]
        self.assertEqual(count_total_chars(messages), 10000)


class TestEstimateTokens(unittest.TestCase):
    def test_default_chars_per_token(self):
        messages = [{"role": "user", "content": "x" * 100}]
        # 100 / 4 = 25
        self.assertEqual(estimate_tokens(messages), 25)

    def test_empty_list_returns_zero(self):
        self.assertEqual(estimate_tokens([]), 0)

    def test_custom_chars_per_token(self):
        messages = [{"role": "user", "content": "x" * 100}]
        self.assertEqual(estimate_tokens(messages, chars_per_token=2), 50)

    def test_rounds_down_via_integer_division(self):
        messages = [{"role": "user", "content": "x" * 9}]
        # 9 // 4 = 2
        self.assertEqual(estimate_tokens(messages), 2)

    def test_single_char(self):
        messages = [{"role": "user", "content": "x"}]
        self.assertEqual(estimate_tokens(messages), 0)

    def test_exactly_four_chars(self):
        messages = [{"role": "user", "content": "xxxx"}]
        self.assertEqual(estimate_tokens(messages), 1)

    def test_custom_small_chars_per_token(self):
        messages = [{"role": "user", "content": "hello"}]
        self.assertEqual(estimate_tokens(messages, chars_per_token=1), 5)

    def test_large_messages_with_blocks(self):
        messages = [
            {"role": "user", "content": "a" * 5000},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "b" * 3000},
                ],
            },
        ]
        # (5000 + 3000) // 4 = 2000
        self.assertEqual(estimate_tokens(messages), 2000)

    def test_high_chars_per_token(self):
        messages = [{"role": "user", "content": "x" * 100}]
        self.assertEqual(estimate_tokens(messages, chars_per_token=10), 10)
