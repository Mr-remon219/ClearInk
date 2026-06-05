"""Tests for clearink.error_recovery.overflow."""

import unittest
from clearink.error_recovery.overflow import is_context_overflow


class TestIsContextOverflow(unittest.TestCase):
    """is_context_overflow returns True when the error message contains
    any of the configured overflow keywords."""

    # ── True cases (known keywords) ─────────────────────────

    def test_context_length(self):
        err = RuntimeError("This exceeds the context length limit")
        self.assertTrue(is_context_overflow(err))

    def test_context_length_underscore(self):
        err = RuntimeError("context_length exceeded")
        self.assertTrue(is_context_overflow(err))

    def test_too_long(self):
        err = ValueError("The prompt is too long")
        self.assertTrue(is_context_overflow(err))

    def test_too_large(self):
        err = Exception("input too large for model")
        self.assertTrue(is_context_overflow(err))

    def test_prompt_keyword(self):
        err = RuntimeError("prompt token count is too high")
        self.assertTrue(is_context_overflow(err))

    def test_max_tokens(self):
        err = Exception("exceeded max tokens")
        self.assertTrue(is_context_overflow(err))

    def test_token_limit(self):
        err = RuntimeError("token limit reached")
        self.assertTrue(is_context_overflow(err))

    def test_reduce_the_length(self):
        err = ValueError("Please reduce the length of your input")
        self.assertTrue(is_context_overflow(err))

    def test_input_length(self):
        err = RuntimeError("input length exceeds maximum")
        self.assertTrue(is_context_overflow(err))

    # ── False cases (generic errors) ────────────────────────

    def test_generic_error(self):
        err = RuntimeError("Something went wrong")
        self.assertFalse(is_context_overflow(err))

    def test_rate_limit_error(self):
        err = Exception("Rate limit exceeded")
        self.assertFalse(is_context_overflow(err))

    def test_authentication_error(self):
        err = PermissionError("Invalid API key")
        self.assertFalse(is_context_overflow(err))

    def test_timeout_error(self):
        err = TimeoutError("Request timed out")
        self.assertFalse(is_context_overflow(err))

    def test_empty_message(self):
        err = Exception("")
        self.assertFalse(is_context_overflow(err))

    def test_unrelated_message(self):
        err = ValueError("division by zero")
        self.assertFalse(is_context_overflow(err))

    def test_case_insensitive_match(self):
        """Keyword matching is case-insensitive."""
        err = RuntimeError("CONTEXT LENGTH exceeded")
        self.assertTrue(is_context_overflow(err))

    def test_partial_word_match(self):
        """Substring matching — 'prompt' matches within 'promptly'."""
        err = RuntimeError("promptly done")
        self.assertTrue(is_context_overflow(err))
