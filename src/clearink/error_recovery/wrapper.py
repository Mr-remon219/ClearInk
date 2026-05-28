from __future__ import annotations
from typing import Any

from .retry import call_with_retry, is_transient_error, RETRY_MAX_ATTEMPTS
from .overflow import is_context_overflow, recover, OVERFLOW_MAX_RETRIES
from .truncation import should_retry, next_max_tokens, TRUNCATION_MAX_RETRIES
from ..context_compact.config import CompactConfig


def safe_api_call(
    client: Any,
    *,
    model: str,
    system: str,
    messages: list,
    tools: list,
    max_tokens: int,
    thinking: dict,
    extra_body: dict,
    config: CompactConfig,
    hook_context: dict,
    compact_round: int,
) -> tuple[Any, list, int]:
    """
    Returns (response, messages, new_compact_round).

    Three-layer recovery:
    - Outer: output truncation (8x max_tokens, max 3 retries)
    - Inner: transient errors (arithmetic backoff) + context overflow (reactive compact)
    """
    current_max_tokens = max_tokens

    for truncation_attempt in range(TRUNCATION_MAX_RETRIES + 1):
        response = None
        overflow_attempt = 0

        while True:
            try:
                response = call_with_retry(
                    client,
                    model=model,
                    system=system,
                    messages=messages,
                    tools=tools,
                    max_tokens=current_max_tokens,
                    thinking=thinking,
                    extra_body=extra_body,
                )
                break
            except Exception as e:
                if is_context_overflow(e) and overflow_attempt < OVERFLOW_MAX_RETRIES:
                    overflow_attempt += 1
                    compact_round += 1
                    messages = recover(
                        messages, config, hook_context, compact_round,
                    )
                    continue
                raise

        if response.stop_reason != "max_tokens":
            return response, messages, compact_round

        if should_retry(truncation_attempt):
            current_max_tokens = next_max_tokens(current_max_tokens)
            continue

        break

    return response, messages, compact_round
