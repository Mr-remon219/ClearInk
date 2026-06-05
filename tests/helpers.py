"""Shared test helpers for ClearInk integration tests.

Pure functions only — no fixtures, no side effects.
Put fixtures in conftest.py instead.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


# ── Mock response builders ──────────────────────────────────

def make_text_block(text: str) -> dict:
    """Create an Anthropic-format text content block."""
    return {"type": "text", "text": text}


def make_tool_use_block(tool_id: str, name: str, input_data: dict) -> dict:
    """Create an Anthropic-format tool_use content block."""
    return {"type": "tool_use", "id": tool_id, "name": name, "input": input_data}


def make_thinking_block(thinking: str, signature: str = "sig") -> dict:
    """Create an Anthropic-format thinking content block."""
    return {"type": "thinking", "thinking": thinking, "signature": signature}


def make_mock_response(stop_reason: str, content: list[dict]) -> MagicMock:
    """Return a MagicMock that looks like an Anthropic Messages response."""
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = content
    return resp


# ── Message builders ────────────────────────────────────────

def make_user_message(content: str | list[dict]) -> dict:
    """Create a user-role message."""
    return {"role": "user", "content": content}


def make_assistant_message(content: list[dict]) -> dict:
    """Create an assistant-role message with content blocks."""
    return {"role": "assistant", "content": content}


def build_conversation(n_turns: int, *, include_tool_results: bool = False) -> list[dict]:
    """Build a pseudo-conversation of *n_turns* user-assistant pairs.

    Each turn:
        user: "Question {i}"
        assistant: text block "Answer {i}"

    If *include_tool_results*, the assistant content alternates between
    a text block and a tool_use block, with a tool_result user message
    after each tool_use.
    """
    messages: list[dict] = []
    for i in range(1, n_turns + 1):
        messages.append(make_user_message(f"Question {i}"))
        if include_tool_results and i % 2 == 1:
            tool_id = f"toolu_{i:04d}"
            messages.append({
                "role": "assistant",
                "content": [make_tool_use_block(tool_id, "read_file", {"file_path": f"doc{i}.txt"})],
            })
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": f"Content of doc{i}.txt\n" * 10,
                }],
            })
        else:
            messages.append(make_assistant_message([make_text_block(f"Answer {i}")]))
    return messages


def build_big_conversation(n_turns: int, big_content_size: int = 6000) -> list[dict]:
    """Build a conversation with some very large text blocks for compaction tests."""
    big_text = "X" * big_content_size
    messages: list[dict] = []
    for i in range(1, n_turns + 1):
        messages.append(make_user_message(f"Question {i}"))
        if i % 5 == 0:
            # Every 5th turn: big tool result
            tid = f"toolu_{i:04d}"
            messages.append({
                "role": "assistant",
                "content": [make_tool_use_block(tid, "read_file", {"file_path": f"big{i}.txt"})],
            })
            messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tid, "content": big_text}],
            })
        else:
            messages.append(make_assistant_message([make_text_block(f"Answer {i}")]))
    return messages


# ── File assertion helpers ──────────────────────────────────

def assert_jsonl_has(path: Path, key: str, expected_value) -> None:
    """Assert that a JSONL file contains at least one line where `entry[key] == expected_value`."""
    import json
    assert path.exists(), f"JSONL file does not exist: {path}"
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get(key) == expected_value:
            return
    raise AssertionError(f"No line in {path} has {key} == {expected_value!r}")


def count_jsonl_lines(path: Path) -> int:
    """Return the number of non-empty lines in a JSONL file."""
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").strip().splitlines() if line.strip())


# ── Deep copy helpers ───────────────────────────────────────

def deep_copy_hooks(original: dict) -> dict:
    """Deep copy the HOOKS registry so we can restore it later."""
    import copy
    return copy.deepcopy(original)


def deep_copy_tool_registry() -> tuple[list[dict], dict]:
    """Deep copy TOOL and TOOL_HANDLERS."""
    import copy
    from clearink.tool.register import TOOL, TOOL_HANDLERS
    return copy.deepcopy(TOOL), copy.deepcopy(TOOL_HANDLERS)
