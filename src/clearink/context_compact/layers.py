"""Context compaction layers — L2 placeholder replacement and exchange utilities.

L1 (middle trimming) and L3 (tool result archiving) have been removed:
  - L1 risked silently dropping DAG task creation/completion records
  - L3 rarely triggered for compact paper-search results (<4000 chars)
"""

from __future__ import annotations

from .config import CompactConfig
from .archive import write_l2_content


# --- Exchange Segmentation ---

def segment_exchanges(messages: list) -> list[list[dict]]:
    """Split a flat message list into exchanges. A new user message
    (not a tool_result batch) starts a new exchange."""
    if not messages:
        return []

    exchanges: list[list[dict]] = []
    current: list[dict] = []

    for msg in messages:
        if not isinstance(msg, dict):
            current.append(msg)
            continue

        if _starts_new_exchange(msg):
            if current:
                exchanges.append(current)
            current = [msg]
        else:
            current.append(msg)

    if current:
        exchanges.append(current)

    return exchanges


def _starts_new_exchange(msg: dict) -> bool:
    if msg.get("role") != "user":
        return False
    content = msg.get("content", "")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        has_tool_result = any(
            isinstance(b, dict) and b.get("type") == "tool_result"
            for b in content
        )
        return not has_tool_result
    return False


def rebuild_messages(exchanges: list[list[dict]]) -> list:
    """Flatten exchange segments back into a single message list."""
    result = []
    for ex in exchanges:
        result.extend(ex)
    return result


# --- L2: Placeholder Replacement ---

_COMPACT_PREFIX = "[Content compacted:"


def layer2_placeholder_large(
    messages: list, config: CompactConfig, round_number: int,
) -> list:
    """Replace large text blocks (>l2_min_chars) with file-reference placeholders.
    Skips the most recent exchange to preserve current context."""
    exchanges = segment_exchanges(messages)
    if not exchanges:
        return messages

    l2_idx = 0

    for i, ex in enumerate(exchanges):
        # Skip the most recent exchange — preserve the latest context intact
        if i == len(exchanges) - 1:
            continue

        for msg in ex:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")

            if isinstance(content, str):
                if _should_replace(content, config):
                    try:
                        filename = write_l2_content(
                            content, config.session_id, round_number, l2_idx,
                            config.transcripts_dir,
                        )
                        msg["content"] = (
                            f"[Content compacted: {len(content)} chars "
                            f"-> see data/.transcripts/{filename}]"
                        )
                        l2_idx += 1
                    except OSError:
                        pass

            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_text = block.get("text") or block.get("content")
                    if not isinstance(block_text, str):
                        continue
                    if _should_replace(block_text, config):
                        key = "text" if "text" in block else "content"
                        try:
                            filename = write_l2_content(
                                block_text, config.session_id, round_number, l2_idx,
                                config.transcripts_dir,
                            )
                            block[key] = (
                                f"[Content compacted: {len(block_text)} chars "
                                f"-> see data/.transcripts/{filename}]"
                            )
                            l2_idx += 1
                        except OSError:
                            pass

    return messages


def _should_replace(text: str, config: CompactConfig) -> bool:
    if len(text) < config.l2_min_chars:
        return False
    if text.startswith(_COMPACT_PREFIX):
        return False
    return True
