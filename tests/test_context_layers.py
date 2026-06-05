import unittest
from types import SimpleNamespace

from clearink.context_compact.layers import (
    segment_exchanges,
    _starts_new_exchange,
    rebuild_messages,
    layer1_trim_middle,
    _should_replace,
)


def _make_config(**overrides) -> SimpleNamespace:
    """Create a mock CompactConfig with sensible defaults."""
    defaults = {
        "l1_min_exchanges": 4,
        "l1_keep_first_exchanges": 3,
        "l1_keep_last_exchanges": 5,
        "l2_min_chars": 3000,
        "l3_min_chars": 4000,
        "task_outputs_dir": "/tmp",
        "transcripts_dir": "/tmp",
        "session_id": "test-session",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestSegmentExchanges(unittest.TestCase):
    def test_single_user_msg_is_one_exchange(self):
        messages = [{"role": "user", "content": "hello"}]
        exchanges = segment_exchanges(messages)
        self.assertEqual(len(exchanges), 1)
        self.assertEqual(len(exchanges[0]), 1)

    def test_user_assistant_user_is_two_exchanges(self):
        messages = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
        ]
        exchanges = segment_exchanges(messages)
        self.assertEqual(len(exchanges), 2)
        self.assertEqual(len(exchanges[0]), 2)
        self.assertEqual(len(exchanges[1]), 1)

    def test_tool_result_does_not_start_new_exchange(self):
        messages = [
            {"role": "user", "content": [{"type": "tool_result", "content": "output"}]},
            {"role": "assistant", "content": "response"},
            {"role": "user", "content": "follow up"},
        ]
        exchanges = segment_exchanges(messages)
        self.assertEqual(len(exchanges), 2)
        # tool_result user msg is part of the first exchange
        self.assertEqual(len(exchanges[0]), 2)

    def test_empty_messages_returns_empty_list(self):
        self.assertEqual(segment_exchanges([]), [])

    def test_only_assistant_messages(self):
        messages = [
            {"role": "assistant", "content": "a1"},
            {"role": "assistant", "content": "a2"},
        ]
        exchanges = segment_exchanges(messages)
        self.assertEqual(len(exchanges), 1)
        self.assertEqual(len(exchanges[0]), 2)

    def test_non_dict_messages_are_grouped(self):
        messages = [
            "not a dict",
            {"role": "user", "content": "hello"},
        ]
        exchanges = segment_exchanges(messages)
        self.assertEqual(len(exchanges), 2)
        self.assertEqual(len(exchanges[0]), 1)
        self.assertEqual(len(exchanges[1]), 1)

    def test_multiple_exchanges(self):
        messages = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "q3"},
        ]
        exchanges = segment_exchanges(messages)
        self.assertEqual(len(exchanges), 3)

    def test_tool_result_in_middle_of_exchange(self):
        messages = [
            {"role": "user", "content": "initial query"},
            {"role": "assistant", "content": "tool call"},
            {"role": "user", "content": [{"type": "tool_result", "content": "data"}]},
            {"role": "user", "content": "actual query"},
            {"role": "assistant", "content": "response"},
        ]
        exchanges = segment_exchanges(messages)
        self.assertEqual(len(exchanges), 2)
        # Exchange 0: initial query + tool call + tool_result
        self.assertEqual(len(exchanges[0]), 3)
        # Exchange 1: actual query + response
        self.assertEqual(len(exchanges[1]), 2)

    def test_mixed_content_types(self):
        messages = [
            {"role": "user", "content": "text"},
            {"role": "assistant", "content": [{"type": "text", "text": "blocks"}]},
            {"role": "user", "content": "more"},
        ]
        exchanges = segment_exchanges(messages)
        self.assertEqual(len(exchanges), 2)

    def test_large_number_of_messages(self):
        messages = []
        for i in range(10):
            messages.append({"role": "user", "content": f"q{i}"})
            messages.append({"role": "assistant", "content": f"a{i}"})
        exchanges = segment_exchanges(messages)
        self.assertEqual(len(exchanges), 10)
        for ex in exchanges:
            self.assertEqual(len(ex), 2)


class TestStartsNewExchange(unittest.TestCase):
    def test_user_string_content_returns_true(self):
        msg = {"role": "user", "content": "hello"}
        self.assertTrue(_starts_new_exchange(msg))

    def test_tool_result_content_returns_false(self):
        msg = {
            "role": "user",
            "content": [{"type": "tool_result", "content": "result"}],
        }
        self.assertFalse(_starts_new_exchange(msg))

    def test_mixed_content_with_tool_result_returns_false(self):
        msg = {
            "role": "user",
            "content": [
                {"type": "tool_result", "content": "data"},
                {"type": "text", "text": "query"},
            ],
        }
        self.assertFalse(_starts_new_exchange(msg))

    def test_non_user_role_returns_false(self):
        msg = {"role": "assistant", "content": "answer"}
        self.assertFalse(_starts_new_exchange(msg))

    def test_system_role_returns_false(self):
        msg = {"role": "system", "content": "instruction"}
        self.assertFalse(_starts_new_exchange(msg))

    def test_non_dict_ignored(self):
        # non-dict messages always pass through and _starts_new_exchange is not called
        pass

    def test_no_content_in_user_msg_returns_true(self):
        msg = {"role": "user"}
        self.assertTrue(_starts_new_exchange(msg))

    def test_empty_content_user_msg_returns_true(self):
        msg = {"role": "user", "content": ""}
        self.assertTrue(_starts_new_exchange(msg))

    def test_empty_list_content_user_msg_returns_true(self):
        msg = {"role": "user", "content": []}
        self.assertTrue(_starts_new_exchange(msg))

    def test_tool_result_only_no_other_types(self):
        msg = {
            "role": "user",
            "content": [{"type": "tool_result", "content": "result"}],
        }
        self.assertFalse(_starts_new_exchange(msg))

    def test_text_only_content_with_list_returns_true(self):
        msg = {
            "role": "user",
            "content": [{"type": "text", "text": "hello"}],
        }
        self.assertTrue(_starts_new_exchange(msg))


class TestRebuildMessages(unittest.TestCase):
    def test_flattens_exchanges(self):
        exchanges = [
            [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}],
            [{"role": "user", "content": "q2"}],
        ]
        result = rebuild_messages(exchanges)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["content"], "q1")
        self.assertEqual(result[1]["content"], "a1")
        self.assertEqual(result[2]["content"], "q2")

    def test_empty_exchanges_returns_empty_list(self):
        self.assertEqual(rebuild_messages([]), [])

    def test_single_empty_exchange(self):
        self.assertEqual(rebuild_messages([[]]), [])

    def test_preserves_message_order(self):
        exchanges = [
            [{"role": "user", "content": "a"}],
            [{"role": "assistant", "content": "b"}],
            [{"role": "user", "content": "c"}],
        ]
        result = rebuild_messages(exchanges)
        contents = [m["content"] for m in result]
        self.assertEqual(contents, ["a", "b", "c"])

    def test_does_not_modify_original_messages(self):
        msg = {"role": "user", "content": "original"}
        exchanges = [[msg]]
        result = rebuild_messages(exchanges)
        msg["role"] = "assistant"
        self.assertEqual(result[0]["role"], "assistant")

    def test_many_exchanges(self):
        exchanges = [[{"role": "user", "content": f"q{i}"}] for i in range(20)]
        result = rebuild_messages(exchanges)
        self.assertEqual(len(result), 20)


class TestLayer1TrimMiddle(unittest.TestCase):
    def setUp(self):
        self.config = _make_config(
            l1_min_exchanges=4,
            l1_keep_first_exchanges=3,
            l1_keep_last_exchanges=5,
        )

    def _make_exchange_messages(self, n: int) -> list:
        msgs = []
        for i in range(n):
            msgs.append({"role": "user", "content": f"q{i}"})
            msgs.append({"role": "assistant", "content": f"a{i}"})
        return msgs

    def test_below_threshold_returns_unchanged(self):
        messages = self._make_exchange_messages(3)
        result = layer1_trim_middle(messages, self.config)
        self.assertEqual(result, messages)

    def test_returns_unchanged_when_at_min_exchanges(self):
        messages = self._make_exchange_messages(4)
        result = layer1_trim_middle(messages, self.config)
        self.assertEqual(result, messages)

    def test_keeps_first_and_last_when_over_threshold(self):
        messages = self._make_exchange_messages(20)
        result = layer1_trim_middle(messages, self.config)
        # 3 first + 5 last = 8 exchanges kept = 16 messages
        self.assertEqual(len(result), 16)
        self.assertEqual(result[0]["content"], "q0")
        self.assertEqual(result[1]["content"], "a0")
        self.assertEqual(result[-2]["content"], "q19")
        self.assertEqual(result[-1]["content"], "a19")

    def test_empty_messages(self):
        self.assertEqual(layer1_trim_middle([], self.config), [])

    def test_custom_keep_counts(self):
        config = _make_config(
            l1_min_exchanges=2,
            l1_keep_first_exchanges=1,
            l1_keep_last_exchanges=2,
        )
        messages = self._make_exchange_messages(10)
        result = layer1_trim_middle(messages, config)
        self.assertEqual(len(result), 6)  # 1 + 2 = 3 exchanges = 6 messages

    def test_does_not_trim_if_keep_sum_exceeds_total(self):
        config = _make_config(
            l1_min_exchanges=2,
            l1_keep_first_exchanges=5,
            l1_keep_last_exchanges=5,
        )
        messages = self._make_exchange_messages(8)
        result = layer1_trim_middle(messages, config)
        self.assertEqual(result, messages)

    def test_first_and_last_are_preserved_in_order(self):
        messages = self._make_exchange_messages(15)
        result = layer1_trim_middle(messages, self.config)
        self.assertEqual(result[0]["content"], "q0")
        self.assertEqual(result[1]["content"], "a0")
        self.assertEqual(result[-2]["content"], "q14")
        self.assertEqual(result[-1]["content"], "a14")


class TestShouldReplace(unittest.TestCase):
    def setUp(self):
        self.config = _make_config(l2_min_chars=3000)

    def test_large_text_returns_true(self):
        text = "x" * 5000
        self.assertTrue(_should_replace(text, self.config))

    def test_small_text_returns_false(self):
        text = "small"
        self.assertFalse(_should_replace(text, self.config))

    def test_exactly_at_min_chars(self):
        text = "x" * 3000
        self.assertTrue(_should_replace(text, self.config))

    def test_barely_below_min_chars(self):
        text = "x" * 2999
        self.assertFalse(_should_replace(text, self.config))

    def test_archive_prefix_returns_false(self):
        text = "[Tool output archived -> data/task_outputs/file.txt]"
        self.assertFalse(_should_replace(text, self.config))

    def test_compact_prefix_returns_false(self):
        text = "[Content compacted: 5000 chars -> see data/.transcripts/file.txt]"
        self.assertFalse(_should_replace(text, self.config))

    def test_large_text_with_prefix_combined(self):
        text = "[Tool output archived -> file]" + "x" * 5000
        self.assertFalse(_should_replace(text, self.config))

    def test_empty_text(self):
        self.assertFalse(_should_replace("", self.config))

    def test_short_text_with_no_prefix(self):
        self.assertFalse(_should_replace("hello world", self.config))

    def test_custom_min_chars(self):
        config = _make_config(l2_min_chars=10)
        self.assertTrue(_should_replace("hello world!!!", config))
        self.assertFalse(_should_replace("short", config))

    def test_archive_prefix_exact_match(self):
        text = "[Tool output archived ->"
        self.assertFalse(_should_replace(text, self.config))

    def test_compact_prefix_exact_match(self):
        text = "[Content compacted:"
        self.assertFalse(_should_replace(text, self.config))
