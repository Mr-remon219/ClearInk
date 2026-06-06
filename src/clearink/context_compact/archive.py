from __future__ import annotations
import json
import warnings
from pathlib import Path


def write_transcript(
    messages: list,
    session_id: str,
    round_number: int,
    transcripts_dir: Path,
) -> Path:
    """Write full conversation to a JSON transcript file. Returns the file path."""
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{session_id}_round{round_number:03d}.json"
    filepath = transcripts_dir / filename
    try:
        filepath.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    except OSError as exc:
        warnings.warn(f"Failed to write transcript {filepath}: {exc}")
        raise
    return filepath


def write_l2_content(
    content: str,
    session_id: str,
    round_number: int,
    idx: int,
    transcripts_dir: Path,
) -> str:
    """Write a single large content block to a separate file (L2 placeholder).

    Caller (compact_messages) has already called ensure_dirs(), so the
    transcripts directory is guaranteed to exist.
    """
    filename = f"{session_id}_round{round_number:03d}_l2_{idx}.txt"
    filepath = transcripts_dir / filename
    try:
        filepath.write_text(content, encoding="utf-8")
    except OSError as exc:
        warnings.warn(f"Failed to write L2 content {filepath}: {exc}")
        raise
    return filename


_SUMMARY_MARKER = "[Compact #"


def read_previous_summary(messages: list) -> str | None:
    """Find the most recent L4 summary in the message list."""
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and content.startswith(_SUMMARY_MARKER):
            return content
    return None
