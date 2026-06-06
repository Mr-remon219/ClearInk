"""Integration tests for the error recovery subsystem.

Tests the retry logic, context overflow detection, truncation handling,
and the combined safe_api_call wrapper across all three recovery layers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from clearink.context_compact.config import CompactConfig
from clearink.error_recovery.overflow import (
    OVERFLOW_MAX_RETRIES,
    is_context_overflow,
)
from clearink.error_recovery.retry import (
    RETRY_MAX_ATTEMPTS,
    call_with_retry,
    is_transient_error,
)
from clearink.error_recovery.truncation import (
    next_max_tokens,
    should_retry,
)
from clearink.error_recovery.wrapper import safe_api_call
from tests.helpers import make_mock_response, make_text_block


# ============================================================
# Retry tests
# ============================================================


def test_transient_error_retry_succeeds():
    """Retry on transient errors: fails twice, succeeds on 3rd call."""
    client = MagicMock()
    transient = Exception("rate limit exceeded")
    success = make_mock_response("end_turn", [make_text_block("OK")])

    client.messages.create.side_effect = [transient, transient, success]

    result = call_with_retry(client, model="test", messages=["hi"])

    assert result is success
    assert client.messages.create.call_count == 3


def test_non_transient_error_fails_immediately():
    """A non-transient error (auth) should raise on the first call."""
    client = MagicMock()
    auth_error = Exception("401 Unauthorized: invalid API key")
    client.messages.create.side_effect = auth_error

    with pytest.raises(Exception, match="401"):
        call_with_retry(client, model="test", messages=["hi"])

    assert client.messages.create.call_count == 1


def test_transient_error_exhausts_retries():
    """A persistent transient error should raise after RETRY_MAX_ATTEMPTS calls."""
    client = MagicMock()
    transient = Exception("rate limit exceeded")
    client.messages.create.side_effect = transient

    with pytest.raises(Exception, match="rate limit"):
        call_with_retry(client, model="test", messages=["hi"])

    assert client.messages.create.call_count == RETRY_MAX_ATTEMPTS


def test_is_transient_error_classification():
    """Verify classification of transient vs non-transient errors."""
    # Transient
    assert is_transient_error(Exception("rate limit exceeded")) is True
    assert is_transient_error(Exception("500 Internal Server Error")) is True
    assert is_transient_error(Exception("Request timed out")) is True

    # Non-transient
    assert is_transient_error(Exception("401 Unauthorized")) is False
    assert is_transient_error(Exception("403 Forbidden")) is False
    assert is_transient_error(Exception("400 Bad Request")) is False


# ============================================================
# Context overflow tests
# ============================================================


def test_is_context_overflow_detection():
    """Verify detection of context overflow error messages."""
    assert is_context_overflow(Exception("prompt is too long")) is True
    assert is_context_overflow(Exception("context_length exceeded")) is True
    assert is_context_overflow(Exception("token limit reached")) is True
    assert is_context_overflow(Exception("reduce the length of the messages")) is True
    assert is_context_overflow(Exception("normal error")) is False


def test_overflow_recovery_triggers_compact():
    """safe_api_call should call reactive_compact when overflow is detected,
    then retry and return the success response.

    NOTE: We must patch wrapper.recover, NOT overflow.recover, because
    wrapper.py does ``from .overflow import recover``, creating a local
    reference that is independent of the module attribute.
    """
    client = MagicMock()

    from clearink.error_recovery import wrapper as wrapper_mod

    original_recover = wrapper_mod.recover

    def fake_recover(messages, config, hook_context, round_number):
        return messages + [{"role": "user", "content": "compacted"}]

    wrapper_mod.recover = fake_recover

    try:
        overflow_error = Exception("prompt is too long")
        success = make_mock_response("end_turn", [make_text_block("success")])

        client.messages.create.side_effect = [overflow_error, success]

        config = CompactConfig()
        result_response, result_messages, result_round = safe_api_call(
            client,
            model="test-model",
            system="You are a test.",
            messages=[{"role": "user", "content": "hello"}],
            tools=[],
            max_tokens=1024,
            thinking=None,
            extra_body=None,
            config=config,
            hook_context={},
            compact_round=0,
        )

        assert result_response is success
        assert result_messages[-1]["content"] == "compacted"
        assert result_round == 1
        assert client.messages.create.call_count == 2
    finally:
        wrapper_mod.recover = original_recover


def test_overflow_max_retries_exceeded():
    """safe_api_call should raise after OVERFLOW_MAX_RETRIES + 1 overflow errors."""
    client = MagicMock()
    overflow_error = Exception("prompt is too long")
    client.messages.create.side_effect = overflow_error

    from clearink.error_recovery import wrapper as wrapper_mod

    original_recover = wrapper_mod.recover

    def fake_recover(messages, config, hook_context, round_number):
        return messages + [{"role": "user", "content": "compacted"}]

    wrapper_mod.recover = fake_recover

    try:
        config = CompactConfig()
        with pytest.raises(Exception, match="prompt is too long"):
            safe_api_call(
                client,
                model="test-model",
                system="You are a test.",
                messages=[{"role": "user", "content": "hello"}],
                tools=[],
                max_tokens=1024,
                thinking=None,
                extra_body=None,
                config=config,
                hook_context={},
                compact_round=0,
            )

        expected_calls = OVERFLOW_MAX_RETRIES + 1
        assert client.messages.create.call_count == expected_calls
    finally:
        wrapper_mod.recover = original_recover


# ============================================================
# Truncation tests
# ============================================================


def test_truncation_should_retry():
    """should_retry returns True for attempts < TRUNCATION_MAX_RETRIES."""
    assert should_retry(0) is True
    assert should_retry(2) is True
    assert should_retry(3) is False  # == TRUNCATION_MAX_RETRIES (3)
    assert should_retry(5) is False


def test_next_max_tokens_calculation():
    """next_max_tokens multiplies by 8 and caps at MAX_TOKENS_CAP."""
    assert next_max_tokens(4096) == 32768  # 4096 * 8 = 32768 == cap
    assert next_max_tokens(1000) == 8000  # 1000 * 8 = 8000
    assert next_max_tokens(5000) == 32768  # 5000 * 8 = 40000 -> capped at 32768


# ============================================================
# Combined recovery (safe_api_call) tests
# ============================================================


def test_safe_api_call_mixed_recovery():
    """Recover first from overflow, then from max_tokens truncation,
    then succeed on the final attempt.

    Sequence:
      1st call            -> context overflow error
      2nd call (after comp) -> stop_reason="max_tokens"  (max_tokens=4096)
      3rd call (after 8x)   -> stop_reason="end_turn"    (success)
    """
    client = MagicMock()

    from clearink.error_recovery import wrapper as wrapper_mod

    original_recover = wrapper_mod.recover

    def fake_recover(messages, config, hook_context, round_number):
        return messages + [{"role": "user", "content": f"compacted_r{round_number}"}]

    wrapper_mod.recover = fake_recover

    try:
        overflow_error = Exception("prompt is too long")
        truncation_response = make_mock_response(
            "max_tokens", [make_text_block("truncated")],
        )
        success_response = make_mock_response(
            "end_turn", [make_text_block("success")],
        )

        client.messages.create.side_effect = [
            overflow_error,        # 1st: overflow
            truncation_response,   # 2nd: truncated at 4096
            success_response,      # 3rd: success
        ]

        config = CompactConfig()
        result_response, result_messages, result_round = safe_api_call(
            client,
            model="test-model",
            system="You are a test.",
            messages=[{"role": "user", "content": "hello"}],
            tools=[],
            max_tokens=4096,
            thinking=None,
            extra_body=None,
            config=config,
            hook_context={},
            compact_round=0,
        )

        assert result_response is success_response
        assert result_round == 1  # incremented by overflow recovery
        assert client.messages.create.call_count == 3

        # Verify the 3rd call used increased max_tokens (4096 * 8 = 32768)
        third_call_kwargs = client.messages.create.call_args_list[2].kwargs
        assert third_call_kwargs["max_tokens"] == 32768
    finally:
        wrapper_mod.recover = original_recover


def test_safe_api_call_sanitizes_thinking_for_non_thinking_requests():
    client = MagicMock()
    success = make_mock_response("end_turn", [make_text_block("success")])
    client.messages.create.return_value = success

    messages = [{
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "hidden"},
            {"type": "text", "text": "visible"},
        ],
    }]

    result_response, result_messages, _ = safe_api_call(
        client,
        model="test-model",
        system="You are a test.",
        messages=messages,
        tools=[],
        max_tokens=1024,
        thinking={"type": "disabled"},
        extra_body=None,
        config=CompactConfig(),
        hook_context={},
        compact_round=0,
    )

    sent_messages = client.messages.create.call_args.kwargs["messages"]
    assert result_response is success
    assert sent_messages == [{
        "role": "assistant",
        "content": [{"type": "text", "text": "visible"}],
    }]
    assert result_messages is messages
