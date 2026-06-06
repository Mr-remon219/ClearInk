"""L4 summarization — produces a compact conversation-state summary."""

from __future__ import annotations
from pathlib import Path


def build_summary(
    previous_summary: str | None,
    transcripts_path: Path,
) -> str:
    """Build a minimal summary: transcript reference + prior state + recent queries.

    Intentionally excludes papers-accessed and other hook_context data —
    that information is not useful for the LLM to understand conversation flow.
    """
    lines = [f"[Compact #{transcripts_path.stem}]", ""]

    if previous_summary:
        # Keep only the first line of the previous summary for continuity
        first_line = previous_summary.split("\n")[0]
        lines.append(f"Prior: {first_line}")
        lines.append("")

    return "\n".join(lines)
