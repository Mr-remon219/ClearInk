from __future__ import annotations
import warnings
from pathlib import Path

from .config import CompactConfig
from .token_estimate import estimate_tokens
from .archive import write_transcript, read_previous_summary
from .summary import build_summary
from .layers import (
    layer3_archive_results,
    layer1_trim_middle,
    layer2_placeholder_large,
    segment_exchanges,
    rebuild_messages,
)


def compact_messages(
    messages: list,
    config: CompactConfig,
    hook_context: dict,
    round_number: int,
) -> list:
    if not messages:
        return messages

    config.ensure_dirs()

    messages = layer3_archive_results(messages, config)
    messages = layer1_trim_middle(messages, config)
    messages = layer2_placeholder_large(messages, config)

    estimated = estimate_tokens(messages, config.token_estimation_chars_per_token)
    if estimated <= config.l4_trigger_tokens:
        return messages

    try:
        transcript_path = write_transcript(
            messages, config.session_id, round_number, config.transcripts_dir,
        )
    except OSError:
        warnings.warn("Failed to write transcript; skipping L4 summarization")
        return messages

    prev_summary = read_previous_summary(messages)
    summary = build_summary(messages, prev_summary, hook_context, transcript_path)

    exchanges = segment_exchanges(messages)
    keep = config.l4_keep_last_exchanges
    kept_exchanges = exchanges[-keep:] if len(exchanges) > keep else exchanges
    kept_messages = rebuild_messages(kept_exchanges)
    kept_messages.insert(0, {"role": "user", "content": summary})

    return kept_messages


def reactive_compact(
    messages: list,
    config: CompactConfig,
    hook_context: dict,
    round_number: int,
) -> list:
    if not messages:
        return messages

    config.ensure_dirs()

    try:
        transcript_path = write_transcript(
            messages, config.session_id, round_number, config.transcripts_dir,
        )
    except OSError:
        warnings.warn("Failed to write transcript; reactive compact without save")
        transcript_path = Path("data/.transcripts/unknown.json")

    prev_summary = read_previous_summary(messages)
    summary = build_summary(messages, prev_summary, hook_context, transcript_path)

    keep = config.reactive_keep_last_messages
    kept = messages[-keep:] if len(messages) > keep else list(messages)
    kept.insert(0, {"role": "user", "content": summary})
    return kept
