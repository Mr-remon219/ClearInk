from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_THINKING_BLOCK_TYPES = {"thinking", "redacted_thinking"}


def content_block_to_dict(block: Any) -> dict:
    """Convert SDK content blocks to JSON-serializable message content."""
    if isinstance(block, Mapping):
        return _jsonify(dict(block))

    if hasattr(block, "model_dump"):
        return _jsonify(block.model_dump(mode="json", exclude_none=True))

    if hasattr(block, "to_dict"):
        return _jsonify(block.to_dict())

    fields = _object_fields(block)
    if fields:
        return _jsonify(fields)

    block_type = getattr(block, "type", None)
    return {"type": str(block_type or type(block).__name__), "text": str(block)}


def content_blocks_to_dicts(blocks: Any) -> list[dict]:
    """Serialize a response content list without dropping provider-specific fields."""
    if blocks is None:
        return []
    return [content_block_to_dict(block) for block in blocks]


def extract_text_from_content(content: Any) -> str:
    """Extract visible text while ignoring thinking/tool blocks."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list | tuple):
        return ""

    parts: list[str] = []
    for block in content:
        block_dict = content_block_to_dict(block)
        if block_dict.get("type") != "text":
            continue
        text = block_dict.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def sanitize_messages_for_no_thinking(messages: list) -> list:
    """Return a copy of messages with thinking blocks removed for non-thinking calls."""
    sanitized = []
    for msg in messages:
        if not isinstance(msg, Mapping):
            sanitized.append(_jsonify(msg))
            continue

        msg_copy = {
            str(key): _jsonify(value)
            for key, value in msg.items()
            if key != "content"
        }
        content = msg.get("content")

        if isinstance(content, str):
            msg_copy["content"] = content
            sanitized.append(msg_copy)
            continue

        if isinstance(content, list | tuple):
            clean_blocks = [
                content_block_to_dict(block)
                for block in content
                if not _is_thinking_block(content_block_to_dict(block))
            ]
            if clean_blocks:
                msg_copy["content"] = clean_blocks
                sanitized.append(msg_copy)
            elif msg_copy.get("role") == "user":
                msg_copy["content"] = ""
                sanitized.append(msg_copy)
            continue

        msg_copy["content"] = _jsonify(content)
        sanitized.append(msg_copy)

    return sanitized


def _jsonify(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonify(v) for v in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if hasattr(value, "model_dump"):
        return _jsonify(value.model_dump(mode="json", exclude_none=True))
    return str(value)


def _object_fields(block: Any) -> dict:
    keys = (
        "type",
        "text",
        "thinking",
        "signature",
        "data",
        "id",
        "name",
        "input",
        "content",
        "caller",
    )
    fields = {}
    for key in keys:
        try:
            value = getattr(block, key)
        except AttributeError:
            continue
        if value is not None:
            fields[key] = value

    try:
        public_vars = {
            str(key): value
            for key, value in vars(block).items()
            if not str(key).startswith("_") and not callable(value)
        }
    except TypeError:
        public_vars = {}

    fields.update(public_vars)
    return fields


def _is_thinking_block(block: dict) -> bool:
    block_type = block.get("type")
    return block_type in _THINKING_BLOCK_TYPES or "thinking" in block
