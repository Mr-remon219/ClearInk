from __future__ import annotations
import json
import warnings
from pathlib import Path


def write_task_output(
    content: str,
    tool_use_id: str,
    exchange_index: int,
    outputs_dir: Path,
) -> str:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    filename = f"exchange{exchange_index}_{tool_use_id}.txt"
    filepath = outputs_dir / filename
    try:
        filepath.write_text(content, encoding="utf-8")
    except OSError as exc:
        warnings.warn(f"Failed to write task output {filepath}: {exc}")
        raise
    return filename


def write_transcript(
    messages: list,
    session_id: str,
    round_number: int,
    transcripts_dir: Path,
) -> Path:
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{session_id}_round{round_number:03d}.json"
    filepath = transcripts_dir / filename
    try:
        filepath.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        warnings.warn(f"Failed to write transcript {filepath}: {exc}")
        raise
    return filepath


def write_l2_content(
    content: str,
    session_id: str,
    idx: int,
    transcripts_dir: Path,
) -> str:
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{session_id}_l2_{idx}.txt"
    filepath = transcripts_dir / filename
    try:
        filepath.write_text(content, encoding="utf-8")
    except OSError as exc:
        warnings.warn(f"Failed to write L2 content {filepath}: {exc}")
        raise
    return filename


_SUMMARY_MARKER = "[Context compacted — full transcript saved to "


def read_previous_summary(messages: list) -> str | None:
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and content.startswith(_SUMMARY_MARKER):
            return content
    return None
