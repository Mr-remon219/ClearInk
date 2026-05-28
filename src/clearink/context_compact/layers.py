from __future__ import annotations
import warnings

from .config import CompactConfig
from .archive import write_task_output, write_l2_content


# --- Exchange Segmentation ---

def segment_exchanges(messages: list) -> list[list[dict]]:
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
    result = []
    for ex in exchanges:
        result.extend(ex)
    return result


# --- L3: Tool Result Archiving ---

_ARCHIVE_PREFIX = "[Tool output archived ->"


def layer3_archive_results(messages: list, config: CompactConfig) -> list:
    exchange_idx = 0
    ex_segments = segment_exchanges(messages)

    for ex in ex_segments:
        for msg in ex:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_result":
                    continue
                block_content = block.get("content", "")
                if not isinstance(block_content, str):
                    continue
                if block_content.startswith(_ARCHIVE_PREFIX):
                    continue
                if len(block_content) < config.l3_min_chars:
                    continue

                tool_id = block.get("tool_use_id", "unknown")
                try:
                    filename = write_task_output(
                        block_content, tool_id, exchange_idx, config.task_outputs_dir,
                    )
                    block["content"] = (
                        f"[Tool output archived -> data/task_outputs/{filename}]"
                    )
                except OSError:
                    pass  # keep original content

        exchange_idx += 1

    return messages


# --- L1: Middle Trimming ---

def layer1_trim_middle(messages: list, config: CompactConfig) -> list:
    exchanges = segment_exchanges(messages)
    if len(exchanges) <= config.l1_min_exchanges:
        return messages

    keep_first = config.l1_keep_first_exchanges
    keep_last = config.l1_keep_last_exchanges
    if keep_first + keep_last >= len(exchanges):
        return messages

    kept = exchanges[:keep_first] + exchanges[-keep_last:]
    return rebuild_messages(kept)


# --- L2: Placeholder Replacement ---

_COMPACT_PREFIX = "[Content compacted:"


def layer2_placeholder_large(
    messages: list, config: CompactConfig,
) -> list:
    exchanges = segment_exchanges(messages)
    if not exchanges:
        return messages

    l2_idx = 0

    for i, ex in enumerate(exchanges):
        if i == len(exchanges) - 1:
            continue  # skip the most recent exchange

        for msg in ex:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")

            if isinstance(content, str):
                if _should_replace(content, config):
                    try:
                        filename = write_l2_content(
                            content, config.session_id, l2_idx, config.transcripts_dir,
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
                                block_text, config.session_id, l2_idx,
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
    if text.startswith(_ARCHIVE_PREFIX):
        return False
    if text.startswith(_COMPACT_PREFIX):
        return False
    return True
