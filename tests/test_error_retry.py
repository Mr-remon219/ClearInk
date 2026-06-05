import unittest
from clearink.error_recovery.retry import is_transient_error, retry_delay

def make_error(msg_text):
    """Create a mock error whose str() contains the given text."""
    class MockError(Exception):
        def __init__(self, text):
            self._text = text
        def __str__(self):
            return self._text
    return MockError(msg_text)

class TestIsTransientError(unittest.TestCase):
    def test_rate_limit(self):
        self.assertTrue(is_transient_error(make_error("rate limit exceeded 429")))

    def test_overloaded(self):
        self.assertTrue(is_transient_error(make_error("server overloaded")))

    def test_server_error(self):
        self.assertTrue(is_transient_error(make_error("internal server error 500")))

    def test_service_unavailable(self):
        self.assertTrue(is_transient_error(make_error("service unavailable 503")))

    def test_auth_error(self):
        self.assertFalse(is_transient_error(make_error("401 unauthorized")))

    def test_forbidden(self):
        self.assertFalse(is_transient_error(make_error("403 forbidden")))

    def test_bad_request(self):
        self.assertFalse(is_transient_error(make_error("400 bad request")))

    def test_timeout(self):
        self.assertTrue(is_transient_error(make_error("connection timed out")))

    def test_connection_error(self):
        self.assertTrue(is_transient_error(make_error("connection error")))

    def test_generic_exception(self):
        self.assertFalse(is_transient_error(Exception("generic error")))


class TestRetryDelay(unittest.TestCase):
    def test_first_attempt(self):
        self.assertAlmostEqual(retry_delay(1), 4.0, places=1)

    def test_second_attempt(self):
        self.assertAlmostEqual(retry_delay(2), 6.0, places=1)

    def test_third_attempt(self):
        self.assertAlmostEqual(retry_delay(3), 8.0, places=1)
