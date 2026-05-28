from __future__ import annotations
import time

RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_DELAY = 2.0  # seconds

_TRANSIENT_KEYWORDS = {
    "rate limit", "rate_limit", "429", "too many requests",
    "server error", "500", "502", "503", "504",
    "timeout", "timed out", "connection",
    "temporarily unavailable", "overloaded",
    "service unavailable",
}

_NON_TRANSIENT_KEYWORDS = {
    "401", "unauthorized", "403", "forbidden",
    "invalid api key", "authentication",
}


def is_transient_error(error: Exception) -> bool:
    msg = str(error).lower()
    for kw in _NON_TRANSIENT_KEYWORDS:
        if kw in msg:
            return False
    for kw in _TRANSIENT_KEYWORDS:
        if kw in msg:
            return True
    return False


def retry_delay(attempt: int) -> float:
    return RETRY_BASE_DELAY * (attempt + 1)


def call_with_retry(client, **kwargs):
    last_error = None
    for attempt in range(RETRY_MAX_ATTEMPTS):
        try:
            return client.messages.create(**kwargs)
        except Exception as e:
            last_error = e
            if not is_transient_error(e):
                raise
            if attempt < RETRY_MAX_ATTEMPTS - 1:
                delay = retry_delay(attempt)
                time.sleep(delay)
    raise last_error
