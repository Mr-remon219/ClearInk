from __future__ import annotations
import warnings

from .config import CompactConfig
from .token_estimate import estimate_tokens
from .archive import write_transcript, read_previous_summary
from .summary import build_summary
from .layers import (
    layer2_placeholder_large,
    segment_exchanges,
    rebuild_messages,
)


def _run_l4_summarization(
    messages: list,
    config: CompactConfig,
    transcript_path,
    keep_fn,
) -> list:
    """Shared L4 summarization: transcript → summary → trim → rebuild → prepend."""
    prev_summary = read_previous_summary(messages)
    summary = build_summary(prev_summary, transcript_path)
    kept = keep_fn(messages, config)
    kept.insert(0, {"role": "user", "content": summary})
    return kept


def _trim_by_exchanges(messages: list, config: CompactConfig) -> list:
    """Keep the last N exchanges (used by scheduled compaction)."""
    exchanges = segment_exchanges(messages)
    keep = config.l4_keep_last_exchanges
    kept_exchanges = exchanges[-keep:] if len(exchanges) > keep else exchanges
    return rebuild_messages(kept_exchanges)


def _trim_by_messages(messages: list, config: CompactConfig) -> list:
    """Keep the last N messages (used by reactive compaction)."""
    keep = config.reactive_keep_last_messages
    exchanges = segment_exchanges(messages)
    kept_exchanges = []
    kept_count = 0
    for exchange in reversed(exchanges):
        kept_exchanges.insert(0, exchange)
        kept_count += len(exchange)
        if kept_count >= keep:
            break
    return rebuild_messages(kept_exchanges)


def compact_messages(
    messages: list,
    config: CompactConfig,
    hook_context: dict,
    round_number: int,
) -> list:
    """Scheduled compaction: L2 placeholder replacement → token check → L4 summarization."""
    if not messages:
        return messages

    config.ensure_dirs()

    # L2: replace large text blocks with file-reference placeholders
    messages = layer2_placeholder_large(messages, config, round_number)

    # Token check — only run L4 if over threshold
    estimated = estimate_tokens(messages, config.token_estimation_chars_per_token)
    if estimated <= config.l4_trigger_tokens:
        return messages

    # L4: summarization
    try:
        transcript_path = write_transcript(
            messages, config.session_id, round_number, config.transcripts_dir,
        )
    except OSError:
        warnings.warn("Failed to write transcript; skipping L4 summarization")
        return messages

    return _run_l4_summarization(
        messages, config, transcript_path, _trim_by_exchanges,
    )


def reactive_compact(
    messages: list,
    config: CompactConfig,
    hook_context: dict,
    round_number: int,
) -> list:
    """Emergency compaction triggered by token threshold — skips L2, goes straight to L4."""
    if not messages:
        return messages

    config.ensure_dirs()

    try:
        transcript_path = write_transcript(
            messages, config.session_id, round_number, config.transcripts_dir,
        )
    except OSError:
        warnings.warn("Failed to write transcript; reactive compact without save")
        transcript_path = config.transcripts_dir / "unknown.json"

    return _run_l4_summarization(
        messages, config, transcript_path, _trim_by_messages,
    )
