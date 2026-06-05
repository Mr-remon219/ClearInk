"""Integration tests for context compaction layers.

Tests cover the full compaction pipeline: exchange segmentation, L1 middle
trimming, L2 placeholder replacement, L3 tool-result archiving, L4 summarization,
and the public ``compact_messages`` entrypoint.
"""

from __future__ import annotations

from pathlib import Path


from clearink.context_compact.config import CompactConfig
from clearink.context_compact.compact import compact_messages
from clearink.context_compact.layers import (
    _should_replace,
    layer1_trim_middle,
    layer2_placeholder_large,
    layer3_archive_results,
    segment_exchanges,
)
from clearink.context_compact.token_estimate import count_total_chars

from tests.helpers import (
    build_big_conversation,
    build_conversation,
    make_assistant_message,
    make_text_block,
    make_tool_use_block,
    make_user_message,
)


# ═══════════════════════════════════════════════════════════════
# 1. L3: Tool Result Archiving
# ═══════════════════════════════════════════════════════════════

class TestL3ArchiveLargeToolResults:
    """layer3_archive_results writes oversized tool_results to disk and replaces
    the content with a short marker."""

    def test_l3_archive_large_tool_results(self, tmp_data_dir: Path):
        tool_id = "toolu_abcd"
        large_content = "A" * 5000  # exceeds default l3_min_chars (4000)

        messages = [
            make_user_message("Question 1"),
            make_assistant_message(
                [make_tool_use_block(tool_id, "read_file", {"path": "big.txt"})]
            ),
            make_user_message([
                {"type": "tool_result", "tool_use_id": tool_id, "content": large_content},
            ]),
            make_assistant_message([make_text_block("Answer 1")]),
        ]

        config = CompactConfig(
            task_outputs_dir=tmp_data_dir / "task_outputs",
            transcripts_dir=tmp_data_dir / ".transcripts",
        )

        result = layer3_archive_results(messages, config)

        # The tool_result block should now contain an archive marker
        tool_msg = result[2]
        tool_block = tool_msg["content"][0]
        assert tool_block["content"].startswith("[Tool output archived ->")

        # A file should have been written to disk
        output_dir = tmp_data_dir / "task_outputs"
        files = sorted(output_dir.iterdir())
        assert len(files) == 1
        written = files[0].read_text(encoding="utf-8")
        assert written == large_content

        # Non-tool messages remain untouched
        assert result[0]["content"] == "Question 1"
        assert result[1]["content"][0]["type"] == "tool_use"
        assert result[3]["content"][0]["text"] == "Answer 1"


# ═══════════════════════════════════════════════════════════════
# 2. L1: Middle Trimming
# ═══════════════════════════════════════════════════════════════

class TestL1TrimMiddle:
    """layer1_trim_middle drops exchanges from the middle of a long conversation."""

    def test_l1_trim_middle_exchanges(self):
        """30 exchanges should be reduced to first 3 + last 5 = 8 exchanges."""
        messages = build_conversation(30)
        config = CompactConfig(
            l1_keep_first_exchanges=3,
            l1_keep_last_exchanges=5,
            l1_min_exchanges=2,
        )

        result = layer1_trim_middle(messages, config)

        # 8 exchanges × 2 messages each = 16 messages
        assert len(result) == 16

        # Verify the retained exchanges by content
        exchanges = segment_exchanges(result)
        assert len(exchanges) == 8

        # First 3 exchanges: "Question 1" … "Question 3"
        assert exchanges[0][0]["content"] == "Question 1"
        assert exchanges[1][0]["content"] == "Question 2"
        assert exchanges[2][0]["content"] == "Question 3"

        # Last 5 exchanges: "Question 26" … "Question 30"
        assert exchanges[3][0]["content"] == "Question 26"
        assert exchanges[4][0]["content"] == "Question 27"
        assert exchanges[5][0]["content"] == "Question 28"
        assert exchanges[6][0]["content"] == "Question 29"
        assert exchanges[7][0]["content"] == "Question 30"

    def test_l1_no_trim_when_few_exchanges(self):
        """5 exchanges should be left unchanged (keep_first + keep_last >= total)."""
        messages = build_conversation(5)
        config = CompactConfig()

        result = layer1_trim_middle(messages, config)

        # With 5 exchanges and keep_first=3, keep_last=5, total kept
        # would be 8 which >= 5, so the function returns the original list.
        assert result is messages
        assert len(result) == 10  # 5 exchanges × 2 messages


# ═══════════════════════════════════════════════════════════════
# 3. L2: Placeholder Replacement
# ═══════════════════════════════════════════════════════════════

class TestL2PlaceholderLarge:
    """layer2_placeholder_large replaces oversized text blocks short markers."""

    def test_l2_placeholder_large_content(self, tmp_data_dir: Path):
        """Large content in a non-newest exchange is replaced."""
        large_text = "X" * 5000  # exceeds default l2_min_chars (3000)

        messages = [
            make_user_message(large_text),
            make_assistant_message([make_text_block("Answer 1")]),
            make_user_message("Question 2"),
            make_assistant_message([make_text_block("Answer 2")]),
        ]

        config = CompactConfig(
            task_outputs_dir=tmp_data_dir / "task_outputs",
            transcripts_dir=tmp_data_dir / ".transcripts",
            session_id="test_l2",
        )

        result = layer2_placeholder_large(messages, config, round_number=1)

        # Exchange 0 (the large text) should be replaced
        assert result[0]["content"].startswith("[Content compacted:")

        # Exchange 1 (the newest) is untouched
        assert result[2]["content"] == "Question 2"

        # A file should have been written
        transcript_dir = tmp_data_dir / ".transcripts"
        files = list(transcript_dir.iterdir())
        assert len(files) == 1
        written = files[0].read_text(encoding="utf-8")
        assert written == large_text

    def test_l2_newest_exchange_protected(self, tmp_data_dir: Path):
        """Large content in the newest exchange is NOT compacted."""
        large_text = "Y" * 5000

        messages = [
            make_user_message("Question 1"),
            make_assistant_message([make_text_block("Answer 1")]),
            make_user_message(large_text),
            make_assistant_message([make_text_block("Answer 2")]),
        ]

        config = CompactConfig(
            task_outputs_dir=tmp_data_dir / "task_outputs",
            transcripts_dir=tmp_data_dir / ".transcripts",
            session_id="test_l2_protect",
        )

        result = layer2_placeholder_large(messages, config, round_number=1)

        # The newest exchange (containing the large text) is not replaced
        assert result[2]["content"] == large_text

        # No L2 content file should have been written
        transcript_dir = tmp_data_dir / ".transcripts"
        files = list(transcript_dir.iterdir()) if transcript_dir.exists() else []
        assert len(files) == 0


# ═══════════════════════════════════════════════════════════════
# 4. L4: Summarization
# ═══════════════════════════════════════════════════════════════

class TestL4Summarization:
    """L4 summarization is triggered when estimated tokens exceed the threshold."""

    def test_l4_summarization_triggered(self, tmp_data_dir: Path):
        """Building enough content triggers summarization — a summary is prepended."""
        messages = build_big_conversation(6, big_content_size=6000)

        config = CompactConfig(
            l4_trigger_tokens=100,          # well below any realistic estimate
            token_estimation_chars_per_token=1,
            l4_keep_last_exchanges=2,
            session_id="test_l4",
            task_outputs_dir=tmp_data_dir / "task_outputs",
            transcripts_dir=tmp_data_dir / ".transcripts",
        )

        result = compact_messages(messages, config, {"papers_accessed": []}, round_number=1)

        # A summary (user role) should be prepended
        assert len(result) > 0
        assert result[0]["role"] == "user"
        summary_text = result[0]["content"]
        assert isinstance(summary_text, str)
        assert summary_text.startswith("[Context compacted — full transcript saved to")

        # A transcript file should have been written
        transcript_dir = tmp_data_dir / ".transcripts"
        files = list(transcript_dir.iterdir())
        transcript_files = [f for f in files if f.suffix == ".json"]
        assert len(transcript_files) >= 1


# ═══════════════════════════════════════════════════════════════
# 5. _should_replace unit-style tests
# ═══════════════════════════════════════════════════════════════

class TestShouldReplace:
    """_should_replace controls which text blocks L2 touches."""

    def test_long_text_returns_true(self):
        config = CompactConfig(l2_min_chars=10)
        assert _should_replace("Hello World This Is Long", config) is True

    def test_archived_text_returns_false(self):
        config = CompactConfig(l2_min_chars=10)
        archived = "[Tool output archived -> data/task_outputs/some_file.txt]"
        assert _should_replace(archived, config) is False

    def test_compacted_text_returns_false(self):
        config = CompactConfig(l2_min_chars=10)
        compacted = "[Content compacted: 4000 chars -> see data/.transcripts/xxx.txt]"
        assert _should_replace(compacted, config) is False

    def test_short_text_returns_false(self):
        config = CompactConfig(l2_min_chars=100)
        assert _should_replace("short", config) is False


# ═══════════════════════════════════════════════════════════════
# 6. Exchange segmentation
# ═══════════════════════════════════════════════════════════════

class TestSegmentExchanges:
    """segment_exchanges correctly groups messages into exchanges."""

    def test_segment_exchanges_correct(self):
        """Tool_result user messages do NOT start new exchanges; regular ones do."""
        messages = [
            make_user_message("Question 1"),                                    # exchange 0 start
            make_assistant_message([make_text_block("Answer 1")]),              # exchange 0
            make_user_message([                                                 # exchange 0 (tool_result)
                {"type": "tool_result", "tool_use_id": "tid_1", "content": "Result 1"},
            ]),
            make_assistant_message([make_text_block("Follow-up")]),             # exchange 0
            make_user_message("Question 2"),                                    # exchange 1 start
            make_assistant_message([make_text_block("Answer 2")]),              # exchange 1
        ]

        exchanges = segment_exchanges(messages)

        assert len(exchanges) == 2

        # Exchange 0: 4 messages (user, assistant, user-with-tool, assistant)
        assert len(exchanges[0]) == 4
        assert exchanges[0][0]["content"] == "Question 1"
        assert exchanges[0][1]["content"][0]["text"] == "Answer 1"
        assert exchanges[0][2]["content"][0]["type"] == "tool_result"
        assert exchanges[0][3]["content"][0]["text"] == "Follow-up"

        # Exchange 1: 2 messages (user, assistant)
        assert len(exchanges[1]) == 2
        assert exchanges[1][0]["content"] == "Question 2"
        assert exchanges[1][1]["content"][0]["text"] == "Answer 2"


# ═══════════════════════════════════════════════════════════════
# 7. Empty messages — all layers are no-ops
# ═══════════════════════════════════════════════════════════════

class TestEmptyMessages:
    """All compaction functions handle empty message lists gracefully."""

    def test_empty_messages_all_layers(self, tmp_data_dir: Path):
        config = CompactConfig(
            task_outputs_dir=tmp_data_dir / "task_outputs",
            transcripts_dir=tmp_data_dir / ".transcripts",
        )

        assert layer3_archive_results([], config) == []
        assert layer1_trim_middle([], config) == []
        assert layer2_placeholder_large([], config, round_number=1) == []
        assert compact_messages([], config, {}, round_number=1) == []


# ═══════════════════════════════════════════════════════════════
# 8. Full pipeline integration
# ═══════════════════════════════════════════════════════════════

class TestCompactMessagesFullPipeline:
    """End-to-end verification of compact_messages."""

    def test_compact_messages_full_pipeline(self, tmp_data_dir: Path):
        messages = build_big_conversation(30, big_content_size=10000)

        original_chars = count_total_chars(messages)

        config = CompactConfig(
            l1_keep_first_exchanges=2,
            l1_keep_last_exchanges=3,
            l1_min_exchanges=3,
            l2_min_chars=3000,
            l3_min_chars=4000,
            l4_trigger_tokens=60000,
            token_estimation_chars_per_token=4,
            session_id="test_pipeline",
            task_outputs_dir=tmp_data_dir / "task_outputs",
            transcripts_dir=tmp_data_dir / ".transcripts",
        )

        result = compact_messages(messages, config, {"papers_accessed": []}, round_number=1)

        # 1. Result is a non-empty list
        assert isinstance(result, list)
        assert len(result) > 0

        # 2. Total characters should be fewer than the original
        result_chars = count_total_chars(result)
        assert result_chars < original_chars, (
            f"Expected fewer chars than {original_chars}, got {result_chars}"
        )

        # 3. Every message has a valid role
        for msg in result:
            assert isinstance(msg, dict)
            assert "role" in msg, f"Message missing 'role': {msg}"
            assert msg["role"] in ("user", "assistant"), (
                f"Unexpected role {msg['role']!r}"
            )

        # 4. Messages follow a valid alternating structure.
        #    After the optional summary prefix (user role), roles must alternate.
        last_role = None
        for msg in result:
            if last_role is not None:
                assert msg["role"] != last_role, (
                    f"Role {msg['role']!r} repeats consecutively"
                )
            last_role = msg["role"]

        # 5. L1 trimming was applied (30 exchanges reduced)
        # With keep_first=2, keep_last=3 we expect at most 5 exchanges
        # (plus potentially the summary prefix)
        total_exchange_count = sum(1 for msg in result if msg["role"] == "assistant")
        kept_assistant_count = config.l1_keep_first_exchanges + config.l1_keep_last_exchanges
        # The summary prefix is a user message that doesn't count as an exchange start
        assert total_exchange_count <= kept_assistant_count
