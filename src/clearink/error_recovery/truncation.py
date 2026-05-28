from __future__ import annotations

TRUNCATION_MAX_RETRIES = 3
TRUNCATION_MULTIPLIER = 8
MAX_TOKENS_CAP = 32768


def should_retry(attempt: int) -> bool:
    return attempt < TRUNCATION_MAX_RETRIES


def next_max_tokens(current: int) -> int:
    nxt = current * TRUNCATION_MULTIPLIER
    return min(nxt, MAX_TOKENS_CAP)
