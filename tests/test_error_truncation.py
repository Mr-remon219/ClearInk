"""Tests for clearink.error_recovery.truncation."""

import unittest
from clearink.error_recovery.truncation import (
    should_retry,
    next_max_tokens,
    TRUNCATION_MAX_RETRIES,
    MAX_TOKENS_CAP,
)


class TestShouldRetry(unittest.TestCase):
    """should_retry returns True for attempts < TRUNCATION_MAX_RETRIES
    and False for attempts >= TRUNCATION_MAX_RETRIES."""

    def test_retry_attempt_1(self):
        self.assertTrue(should_retry(0))

    def test_retry_attempt_2(self):
        self.assertTrue(should_retry(1))

    def test_retry_attempt_3(self):
        self.assertTrue(should_retry(2))

    def test_no_retry_attempt_4(self):
        self.assertFalse(should_retry(3))

    def test_no_retry_attempt_5(self):
        self.assertFalse(should_retry(4))

    def test_no_retry_high_attempt(self):
        self.assertFalse(should_retry(100))

    def test_negative_attempt(self):
        self.assertTrue(should_retry(-1))

    def test_boundary_at_max_retries(self):
        """TRUNCATION_MAX_RETRIES itself should not be retried."""
        self.assertFalse(should_retry(TRUNCATION_MAX_RETRIES))


class TestNextMaxTokens(unittest.TestCase):
    """next_max_tokens doubles with TRUNCATION_MULTIPLIER and caps at MAX_TOKENS_CAP."""

    def test_step_4096_to_32768(self):
        result = next_max_tokens(4096)
        self.assertEqual(result, 32768)

    def test_cap_not_exceeded_above_cap(self):
        """When current * multiplier exceeds MAX_TOKENS_CAP, the cap is returned."""
        result = next_max_tokens(MAX_TOKENS_CAP)
        self.assertEqual(result, MAX_TOKENS_CAP)

    def test_cap_at_32768(self):
        result = next_max_tokens(16384)
        self.assertEqual(result, MAX_TOKENS_CAP)

    def test_small_value(self):
        result = next_max_tokens(1)
        self.assertEqual(result, 8)

    def test_zero_current(self):
        result = next_max_tokens(0)
        self.assertEqual(result, 0)

    def test_large_value_capped(self):
        result = next_max_tokens(100000)
        self.assertEqual(result, MAX_TOKENS_CAP)

    def test_exact_cap_input(self):
        result = next_max_tokens(4096)
        self.assertEqual(result, MAX_TOKENS_CAP)

    def test_negative_current(self):
        result = next_max_tokens(-1)
        self.assertEqual(result, -8)

    def test_max_tokens_cap_constant(self):
        self.assertEqual(MAX_TOKENS_CAP, 32768)
