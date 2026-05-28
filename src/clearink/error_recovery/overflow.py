from __future__ import annotations

OVERFLOW_MAX_RETRIES = 2

_OVERFLOW_KEYWORDS = {
    "prompt", "too long", "too large",
    "context length", "context_length",
    "max tokens", "token limit",
    "reduce the length", "input length",
}


def is_context_overflow(error: Exception) -> bool:
    msg = str(error).lower()
    for kw in _OVERFLOW_KEYWORDS:
        if kw in msg:
            return True
    return False


def recover(
    messages: list,
    config,
    hook_context: dict,
    round_number: int,
) -> list:
    from ..context_compact.compact import reactive_compact
    return reactive_compact(messages, config, hook_context, round_number)
