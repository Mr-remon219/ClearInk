from __future__ import annotations


def count_total_chars(messages: list) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "") if isinstance(msg, dict) else ""
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text") or block.get("content") or ""
                    if isinstance(text, str):
                        total += len(text)
    return total


def estimate_tokens(messages: list, chars_per_token: int = 4) -> int:
    return count_total_chars(messages) // chars_per_token
