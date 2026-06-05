import unittest
from datetime import datetime
from clearink.tool.scheduler.core import cron_matches, _match_field
from clearink.tool.scheduler.tools import _validate_cron_field, _validate_value

class TestCronMatches(unittest.TestCase):
    def test_any_minute(self):
        dt = datetime(2026, 6, 15, 14, 30)
        self.assertTrue(cron_matches("* * * * *", dt))

    def test_exact_match(self):
        dt = datetime(2026, 6, 15, 14, 30)
        self.assertTrue(cron_matches("30 14 15 6 1", dt))

    def test_wrong_minute(self):
        dt = datetime(2026, 6, 15, 14, 31)
        self.assertFalse(cron_matches("30 14 15 6 1", dt))

    def test_step_star(self):
        dt = datetime(2026, 6, 15, 14, 10)
        self.assertTrue(cron_matches("*/5 * * * *", dt))

    def test_step_star_not_match(self):
        dt = datetime(2026, 6, 15, 14, 7)
        self.assertFalse(cron_matches("*/5 * * * *", dt))

    def test_comma_list(self):
        dt = datetime(2026, 6, 15, 14, 30)
        self.assertTrue(cron_matches("0,30 * * * *", dt))

    def test_comma_list_not_match(self):
        dt = datetime(2026, 6, 15, 14, 15)
        self.assertFalse(cron_matches("0,30 * * * *", dt))

    def test_range_match(self):
        dt = datetime(2026, 6, 15, 14, 15)
        self.assertTrue(cron_matches("10-20 * * * *", dt))

    def test_invalid_cron_too_few_fields(self):
        dt = datetime(2026, 6, 15, 14, 30)
        self.assertFalse(cron_matches("* * * *", dt))

    def test_invalid_value_returns_false(self):
        dt = datetime(2026, 6, 15, 14, 59)
        self.assertFalse(cron_matches("60 * * * *", dt))


class TestMatchField(unittest.TestCase):
    def test_star(self):
        self.assertTrue(_match_field("*", 42))

    def test_step_match(self):
        self.assertTrue(_match_field("*/5", 10))

    def test_step_no_match(self):
        self.assertFalse(_match_field("*/5", 7))

    def test_range_match(self):
        self.assertTrue(_match_field("1-5", 3))

    def test_range_no_match(self):
        self.assertFalse(_match_field("1-5", 6))

    def test_comma_match(self):
        self.assertTrue(_match_field("1,3,5", 3))

    def test_comma_no_match(self):
        self.assertFalse(_match_field("1,3,5", 2))

    def test_exact_match(self):
        self.assertTrue(_match_field("42", 42))

    def test_exact_no_match(self):
        self.assertFalse(_match_field("42", 41))


class TestValidateCron(unittest.TestCase):
    def test_validate_value_ok(self):
        _validate_value(5, 0, 59)

    def test_validate_value_too_low(self):
        with self.assertRaises(ValueError):
            _validate_value(-1, 0, 59)

    def test_validate_value_too_high(self):
        with self.assertRaises(ValueError):
            _validate_value(60, 0, 59)

    def test_validate_field_star(self):
        _validate_cron_field("*", 0, 59)

    def test_validate_field_step(self):
        _validate_cron_field("*/5", 0, 59)

    def test_validate_field_step_zero(self):
        with self.assertRaises(ValueError):
            _validate_cron_field("*/0", 0, 59)

    def test_validate_field_range(self):
        _validate_cron_field("10-20", 0, 59)

    def test_validate_field_comma(self):
        _validate_cron_field("1,3,5", 0, 59)
