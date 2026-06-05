"""Integration tests for the core agent_loop function in clearink.main.

These tests verify the full message loop: model checks, hooks, tool execution,
background tasks, context compaction, memory loading, error recovery, and the
end-to-end tool_use -> tool_result roundtrip.
"""

from __future__ import annotations

from clearink.main import agent_loop
from clearink.tool import background as bg_module
from clearink.tool.register import TOOL, TOOL_HANDLERS
from tests.helpers import (
    make_mock_response,
    make_text_block,
    make_tool_use_block,
    make_user_message,
)

# ---------------------------------------------------------------------------
# Shared fixture -- mock expensive / sub-agent dependencies for all tests
# ---------------------------------------------------------------------------

import pytest  # noqa: E402 (import after agent_loop is fine, pytest handles it)


@pytest.fixture(autouse=True)
def _mock_expensive_deps(mocker):
    """Prevent sub-agent LLM calls, MCP assembly, and system-prompt file reads."""
    mocker.patch("clearink.main.load_memories", return_value="")
    mocker.patch("clearink.main.extract_memories", return_value=[])
    mocker.patch("clearink.main.consolidate_memories", return_value="")
    mocker.patch("clearink.main.assemble_tool_pool", return_value=([], {}))
    mocker.patch("clearink.main.get_system_prompt", return_value="System prompt.")


# ---------------------------------------------------------------------------
# Helper assertions
# ---------------------------------------------------------------------------

def _tool_result_messages(result: list) -> list[dict]:
    """Return all user messages that contain a ``tool_result`` block."""
    found: list[dict] = []
    for msg in result:
        if msg["role"] != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        if any(
            isinstance(b, dict) and b.get("type") == "tool_result"
            for b in content
        ):
            found.append(msg)
    return found


def _assistant_messages(result: list) -> list[dict]:
    return [m for m in result if m["role"] == "assistant"]


# ===================================================================
# 1.  End turn  --  basic happy path
# ===================================================================

def test_end_turn_returns_messages(mock_anthropic):
    """Verify agent_loop returns messages when the API ends turn normally."""
    mock_anthropic.side_effect = [
        make_mock_response("end_turn", [make_text_block("Hello from test")]),
    ]

    messages = [make_user_message("Test question")]
    result = agent_loop(messages)

    # The original user message must be present
    assert len(result) >= 2
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "Test question"

    # The final assistant response must contain the expected text
    last = result[-1]
    assert last["role"] == "assistant"
    text = str(last["content"])
    assert "Hello from test" in text


# ===================================================================
# 2.  Single tool-use roundtrip
# ===================================================================

def test_single_tool_use_roundtrip(mock_anthropic, tmp_path):
    """Verify one tool_use is executed and its result is in the history."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello from test file", encoding="utf-8")

    mock_anthropic.side_effect = [
        make_mock_response(
            "tool_use",
            [
                make_tool_use_block(
                    "call_1", "read_file", {"file_path": str(test_file)},
                ),
            ],
        ),
        make_mock_response("end_turn", [make_text_block("Done reading.")]),
    ]

    messages = [make_user_message("Read the file")]
    result = agent_loop(messages)

    # -- tool_use assistant message exists
    assy = _assistant_messages(result)
    tool_use_found = False
    for m in assy:
        for block in (m.get("content") or []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_use_found = True
                break
    assert tool_use_found, "Expected at least one tool_use block in assistant messages"

    # -- tool_result user message with real file content
    tmr = _tool_result_messages(result)
    assert len(tmr) >= 1, "Expected at least one tool_result user message"
    t_content = str(tmr[-1].get("content", ""))
    assert "Hello from test file" in t_content


# ===================================================================
# 3.  Multi-turn tool use  (glob -> read_file -> end_turn)
# ===================================================================

def test_multi_turn_tool_use(mock_anthropic, tmp_path):
    """Verify the loop can process multiple tool_use turns in sequence."""
    # Files for glob to discover
    (tmp_path / "doc1.txt").write_text("Content 1", encoding="utf-8")
    (tmp_path / "doc2.txt").write_text("Content 2", encoding="utf-8")

    mock_anthropic.side_effect = [
        make_mock_response(
            "tool_use",
            [
                make_tool_use_block(
                    "call_g", "glob",
                    {"pattern": "*.txt", "path": str(tmp_path)},
                ),
            ],
        ),
        make_mock_response(
            "tool_use",
            [
                make_tool_use_block(
                    "call_r", "read_file",
                    {"file_path": str(tmp_path / "doc1.txt")},
                ),
            ],
        ),
        make_mock_response("end_turn", [make_text_block("Here's what I found.")]),
    ]

    messages = [make_user_message("Find and read a file")]
    result = agent_loop(messages)

    assy = _assistant_messages(result)
    tmr = _tool_result_messages(result)

    # 3 assistant messages: tool_use (glob) text, tool_use (read_file) text, final text
    assert len(assy) >= 3, (
        f"Expected at least 3 assistant messages, got {len(assy)}"
    )
    # 2 tool_result user messages: glob result, read_file result
    assert len(tmr) >= 2, (
        f"Expected at least 2 tool_result messages, got {len(tmr)}"
    )


# ===================================================================
# 4.  MODEL not set  --  configuration error
# ===================================================================

def test_model_not_set_returns_error(mock_anthropic, monkeypatch):
    """Verify the loop rejects requests when MODEL env var is unset."""
    monkeypatch.delenv("MODEL", raising=False)

    messages = [make_user_message("Test")]
    result = agent_loop(messages)

    assert len(result) >= 1
    last = result[-1]
    assert last["role"] == "assistant"
    content = str(last["content"])
    assert "MODEL" in content
    assert "Configuration error" in content


# ===================================================================
# 5.  API exception  --  safe_api_call propagates
# ===================================================================

def test_api_exception_returns_error(mock_anthropic, mocker):
    """Verify an exception from safe_api_call produces an error message."""
    mocker.patch(
        "clearink.main.safe_api_call",
        side_effect=Exception("test failure"),
    )

    messages = [make_user_message("Test")]
    result = agent_loop(messages)

    assert len(result) >= 2
    last = result[-1]
    assert last["role"] == "assistant"
    content = str(last["content"])
    assert "API call failed after retries" in content
    assert "test failure" in content


# ===================================================================
# 6.  max_tokens stop_reason  --  truncation error
# ===================================================================

def test_max_tokens_returns_error(mock_anthropic):
    """Verify the loop appends a truncation error when max_tokens is hit."""
    # TRUNCATION_MAX_RETRIES=3 → 4 attempts total (0,1,2,3).
    # Provide enough responses so safe_api_call exhausts retries
    # and returns the last max_tokens response.
    mock_anthropic.side_effect = [
        make_mock_response("max_tokens", []),
    ] * 4

    messages = [make_user_message("Test")]
    result = agent_loop(messages)

    assert len(result) >= 2
    last = result[-1]
    assert last["role"] == "assistant"
    content = str(last["content"])
    assert "truncated" in content.lower()
    assert "max token" in content.lower()


# ===================================================================
# 7.  Unknown stop_reason  --  no tool_use blocks
# ===================================================================

def test_unknown_stop_reason_returns_error(mock_anthropic):
    """Verify an unrecognised stop_reason without tool_use blocks raises an error."""
    mock_anthropic.side_effect = [
        make_mock_response(
            "some_weird_reason", [make_text_block("Hello")],
        ),
    ]

    messages = [make_user_message("Test")]
    result = agent_loop(messages)

    assert len(result) >= 2
    last = result[-1]
    assert last["role"] == "assistant"
    content = str(last["content"])
    assert "Unexpected stop_reason" in content
    assert "some_weird_reason" in content


# ===================================================================
# 8.  Unknown tool handler  --  continues gracefully
# ===================================================================

def test_unknown_tool_handler(mock_anthropic):
    """Verify the loop handles an unregistered tool name without crashing."""
    mock_anthropic.side_effect = [
        make_mock_response(
            "tool_use",
            [make_tool_use_block("call_x", "nonexistent_tool_xyz", {})],
        ),
        make_mock_response("end_turn", [make_text_block("Continuing...")]),
    ]

    messages = [make_user_message("Test unknown tool")]
    result = agent_loop(messages)

    # -- tool_result must contain the "Unknown tool" message
    tmr = _tool_result_messages(result)
    assert len(tmr) >= 1, "Expected at least one tool_result message"

    unknown_found = False
    for msg in tmr:
        for block in msg.get("content", []):
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and "Unknown tool" in str(block.get("content", ""))
                and "nonexistent_tool_xyz" in str(block.get("content", ""))
            ):
                unknown_found = True
    assert unknown_found, (
        "Tool result must contain 'Unknown tool: nonexistent_tool_xyz'"
    )

    # -- the loop continued for another turn (end_turn)
    assy = _assistant_messages(result)
    assert len(assy) >= 2, (
        "Loop should continue after handling an unknown tool"
    )


# ===================================================================
# 9.  Tool handler raises exception  --  error captured in tool_result
# ===================================================================

def test_tool_handler_raises_exception(mock_anthropic):
    """Verify an exception from a tool handler is captured in tool_result."""
    # Temporarily register a handler that always raises
    def _failing_handler(**kwargs):
        raise RuntimeError("Intentional failure in test tool")

    TOOL_HANDLERS["_test_fail"] = _failing_handler
    TOOL.append({
        "name": "_test_fail",
        "description": "Tool that always fails",
        "input_schema": {"type": "object", "properties": {}},
    })

    mock_anthropic.side_effect = [
        make_mock_response(
            "tool_use",
            [make_tool_use_block("call_f", "_test_fail", {})],
        ),
        make_mock_response("end_turn", [make_text_block("After failure.")]),
    ]

    messages = [make_user_message("Test failing tool")]
    result = agent_loop(messages)

    # -- tool_result must contain the exception message
    tmr = _tool_result_messages(result)
    error_found = False
    for msg in tmr:
        for block in msg.get("content", []):
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and "Intentional failure" in str(block.get("content", ""))
            ):
                error_found = True
    assert error_found, (
        "Tool result must contain the exception string"
    )

    # -- the loop continued for another turn
    assy = _assistant_messages(result)
    assert len(assy) >= 2, "Loop should continue after a tool handler exception"


# ===================================================================
# 10.  Background task dispatch
# ===================================================================

def test_background_task_dispatch(mock_anthropic, mocker):
    """Verify background task dispatch: start_background_task is called.

    Background tasks run in daemon threads — we mock collection to return
    a known message so the test is deterministic and doesn't race threads.
    """
    start_spy = mocker.spy(bg_module, "start_background_task")

    # Override collect_background_results to return a known result.
    # The spy on the original is replaced, so we don't spy on it.
    mocker.patch.object(
        bg_module, "collect_background_results",
        return_value=["[Background] Task bg_1 (run_bash) done:\ncollect_called"],
    )

    mock_anthropic.side_effect = [
        make_mock_response(
            "tool_use",
            [
                make_tool_use_block(
                    "call_bg", "run_bash",
                    {
                        "command": "echo bg_test",
                        "run_in_background": True,
                    },
                ),
            ],
        ),
        make_mock_response("end_turn", [make_text_block("Done.")]),
    ]

    messages = [make_user_message("Run in background")]
    result = agent_loop(messages)

    assert start_spy.call_count >= 1, (
        "start_background_task should have been called"
    )

    bg_result_found = False
    for msg in result:
        if msg["role"] != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and "collect_called" in content:
            bg_result_found = True
            break
    assert bg_result_found, (
        "Background task result should appear in messages"
    )
