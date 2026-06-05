import unittest
from pathlib import Path

from clearink.context_compact.summary import (
    _extract_recent_user_texts,
    _extract_key_topics,
    _extract_decisions,
    build_summary,
)


class TestExtractRecentUserTexts(unittest.TestCase):
    def test_returns_last_n_user_texts(self):
        messages = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "third"},
        ]
        texts = _extract_recent_user_texts(messages, limit=2)
        self.assertEqual(texts, ["second", "third"])

    def test_returns_all_if_fewer_than_limit(self):
        messages = [
            {"role": "user", "content": "only"},
        ]
        texts = _extract_recent_user_texts(messages, limit=5)
        self.assertEqual(texts, ["only"])

    def test_skips_non_dict_messages(self):
        messages = [
            "not a dict",
            {"role": "user", "content": "real"},
        ]
        texts = _extract_recent_user_texts(messages, limit=5)
        self.assertEqual(texts, ["real"])

    def test_skips_empty_content(self):
        messages = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "valid"},
        ]
        texts = _extract_recent_user_texts(messages, limit=5)
        self.assertEqual(texts, ["valid"])

    def test_returns_empty_list_for_no_messages(self):
        self.assertEqual(_extract_recent_user_texts([], limit=3), [])

    def test_returns_empty_list_for_no_user_messages(self):
        messages = [
            {"role": "assistant", "content": "a1"},
            {"role": "assistant", "content": "a2"},
        ]
        self.assertEqual(_extract_recent_user_texts(messages, limit=3), [])

    def test_limit_one_returns_only_last(self):
        messages = [
            {"role": "user", "content": "q1"},
            {"role": "user", "content": "q2"},
            {"role": "user", "content": "q3"},
        ]
        texts = _extract_recent_user_texts(messages, limit=1)
        self.assertEqual(texts, ["q3"])

    def test_preserves_order(self):
        messages = [
            {"role": "user", "content": "a"},
            {"role": "user", "content": "b"},
            {"role": "user", "content": "c"},
        ]
        texts = _extract_recent_user_texts(messages, limit=3)
        self.assertEqual(texts, ["a", "b", "c"])

    def test_skips_non_string_content(self):
        messages = [
            {"role": "user", "content": ["list", "content"]},
            {"role": "user", "content": "string-content"},
        ]
        texts = _extract_recent_user_texts(messages, limit=5)
        self.assertEqual(texts, ["string-content"])


class TestExtractKeyTopics(unittest.TestCase):
    def test_returns_top_tf_words(self):
        texts = [
            "machine learning model training",
            "learning model evaluation",
            "model training data",
        ]
        topics = _extract_key_topics(texts)
        # "model" appears 3 times, "learning" 2 times, "training" 2 times
        self.assertIn("model", topics)
        self.assertIn("learning", topics)
        self.assertIn("training", topics)

    def test_filters_stop_words(self):
        texts = ["the a is of in the a is of"]
        topics = _extract_key_topics(texts)
        self.assertEqual(topics, [])

    def test_empty_texts(self):
        self.assertEqual(_extract_key_topics([]), [])

    def test_ignores_words_shorter_than_3_chars(self):
        texts = ["hi yo ok on at"]
        topics = _extract_key_topics(texts)
        self.assertEqual(topics, [])

    def test_lowercases_all_words(self):
        texts = ["Machine Learning Model", "Machine Learning Model"]
        topics = _extract_key_topics(texts)
        # Each word appears twice, all >= 3 chars, none are stop words
        self.assertEqual(topics, ["machine", "learning", "model"])

    def test_strips_punctuation(self):
        texts = ["model; learning, machine!", "model; learning, machine!"]
        topics = _extract_key_topics(texts)
        self.assertEqual(topics, ["model", "learning", "machine"])

    def test_returns_top_5_topics(self):
        texts = ["a b c d e f g"] * 10
        self.assertLessEqual(len(_extract_key_topics(texts)), 5)

    def test_only_words_appearing_at_least_twice(self):
        texts = ["unique_word_only_once", "common common"]
        topics = _extract_key_topics(texts)
        self.assertIn("common", topics)
        self.assertNotIn("unique_word_only_once", topics)

    def test_mixed_case_with_punctuation(self):
        texts = [
            "Quantum Computing (QC) is revolutionary!",
            "QC quantum computing advances",
        ]
        topics = _extract_key_topics(texts)
        self.assertIn("quantum", topics)
        self.assertIn("computing", topics)

    def test_single_word_repeated(self):
        texts = ["research research research"]
        topics = _extract_key_topics(texts)
        self.assertEqual(topics, ["research"])


class TestExtractDecisions(unittest.TestCase):
    def test_finds_decide_keyword(self):
        texts = ["We decided to use transformer model."]
        decisions = _extract_decisions(texts)
        self.assertTrue(any("decided" in d.lower() for d in decisions))

    def test_finds_conclusion_keyword(self):
        texts = ["In conclusion, gradient descent works best."]
        decisions = _extract_decisions(texts)
        self.assertTrue(any("conclusion" in d.lower() for d in decisions))

    def test_finds_selected_keyword(self):
        texts = ["We selected the Adam optimizer."]
        decisions = _extract_decisions(texts)
        self.assertTrue(any("selected" in d.lower() for d in decisions))

    def test_finds_chose_keyword(self):
        texts = ["We chose to use dropout regularization."]
        decisions = _extract_decisions(texts)
        self.assertTrue(any("chose" in d.lower() for d in decisions))

    def test_finds_therefore_keyword(self):
        texts = ["Therefore, we need more data."]
        decisions = _extract_decisions(texts)
        self.assertTrue(any("therefore" in d.lower() for d in decisions))

    def test_no_decision_keywords(self):
        texts = ["The sky is blue.", "Water is wet."]
        decisions = _extract_decisions(texts)
        self.assertEqual(decisions, [])

    def test_empty_texts(self):
        self.assertEqual(_extract_decisions([]), [])

    def test_limits_to_3_decisions(self):
        texts = [
            "We decided on approach A. We decided on approach B. "
            "We decided on approach C. We decided on approach D."
        ]
        decisions = _extract_decisions(texts)
        self.assertLessEqual(len(decisions), 3)

    def test_splits_on_question_marks(self):
        texts = ["What should we decide? We chosen option A."]
        decisions = _extract_decisions(texts)
        self.assertTrue(any("chosen" in d.lower() for d in decisions))

    def test_splits_on_exclamation_marks(self):
        texts = ["We decided! This is the conclusion."]
        decisions = _extract_decisions(texts)
        self.assertTrue(any("conclusion" in d.lower() for d in decisions))

    def test_avoids_duplicate_decisions(self):
        texts = [
            "We decided to use method X. We decided to use method X.",
        ]
        decisions = _extract_decisions(texts)
        # "We decided to use method X" only appears once
        self.assertEqual(len(decisions), 1)

    def test_truncates_long_sentences(self):
        long_sentence = "We decided to " + "x" * 300
        texts = [long_sentence]
        decisions = _extract_decisions(texts)
        for d in decisions:
            self.assertLessEqual(len(d), 200)

    def test_keyword_opted(self):
        texts = ["We opted for a simpler solution."]
        decisions = _extract_decisions(texts)
        self.assertTrue(any("opted" in d.lower() for d in decisions))

    def test_keyword_agreed(self):
        texts = ["The team agreed on the architecture."]
        decisions = _extract_decisions(texts)
        self.assertTrue(any("agreed" in d.lower() for d in decisions))


class TestBuildSummary(unittest.TestCase):
    def setUp(self):
        self.messages = [
            {"role": "user", "content": "What is backpropagation?"},
            {"role": "assistant", "content": "Backpropagation is an algorithm."},
        ]
        self.hook_context = {"papers_accessed": []}
        self.transcripts_path = Path("summary-abc123.txt")

    def test_includes_transcript_note(self):
        result = build_summary(
            self.messages, None, self.hook_context, self.transcripts_path,
        )
        self.assertIn("summary-abc123.txt", result)

    def test_includes_previous_summary_when_provided(self):
        result = build_summary(
            self.messages, "=== Previous Summary ===", self.hook_context,
            self.transcripts_path,
        )
        self.assertIn("Previous Summary", result)

    def test_skips_previous_summary_when_none(self):
        result = build_summary(
            self.messages, None, self.hook_context, self.transcripts_path,
        )
        self.assertNotIn("Previous Summary", result)

    def test_includes_topics_when_detected(self):
        messages = [
            {"role": "user", "content": "machine learning model training"},
            {"role": "assistant", "content": "OK"},
            {"role": "user", "content": "deep learning model optimization"},
        ]
        result = build_summary(
            messages, None, self.hook_context, self.transcripts_path,
        )
        self.assertIn("Topics:", result)

    def test_includes_decisions_when_detected(self):
        messages = [
            {"role": "user", "content": "We decided to use gradient descent."},
        ]
        result = build_summary(
            messages, None, self.hook_context, self.transcripts_path,
        )
        self.assertIn("Decisions:", result)

    def test_no_topics_or_decisions_fallback(self):
        messages = [
            {"role": "user", "content": "hi"},
        ]
        result = build_summary(
            messages, None, self.hook_context, self.transcripts_path,
        )
        self.assertIn("no significant topics or decisions", result)

    def test_recently_accessed_papers_included(self):
        hook_ctx = {
            "papers_accessed": [
                {"name": "Paper A", "path": "papers/a.pdf", "access_count": 3},
            ]
        }
        result = build_summary(
            self.messages, None, hook_ctx, self.transcripts_path,
        )
        self.assertIn("Recently Accessed", result)
        self.assertIn("Paper A", result)

    def test_no_papers_no_recent_section(self):
        result = build_summary(
            self.messages, None, self.hook_context, self.transcripts_path,
        )
        self.assertNotIn("Recently Accessed", result)

    def test_papers_truncated_to_last_10(self):
        hook_ctx = {
            "papers_accessed": [
                {"name": f"Paper {i}", "path": f"p{i}.pdf", "access_count": 1}
                for i in range(20)
            ]
        }
        result = build_summary(
            self.messages, None, hook_ctx, self.transcripts_path,
        )
        # Only last 10 should appear
        self.assertIn("Paper 10", result)
        self.assertNotIn("Paper 0", result)

    def test_returns_string(self):
        result = build_summary(
            self.messages, None, self.hook_context, self.transcripts_path,
        )
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
