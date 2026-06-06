from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from clearink.config import TRANSCRIPTS_DIR


@dataclass
class CompactConfig:
    """Configuration for context compaction.

    Two layers remain (L1 and L3 removed as unnecessary):
      L2 — replaces large text blocks with file references
      L4 — summarizes conversation and keeps last few exchanges
    """

    # L2: Placeholder Replacement
    l2_min_chars: int = 3000

    # Token Check
    token_estimation_chars_per_token: int = 4
    l4_trigger_tokens: int = 60000

    # L4: Summarization
    l4_keep_last_exchanges: int = 3

    # Reactive Compact
    reactive_keep_last_messages: int = 10
    reactive_trigger_tokens: int = 100000

    # Scheduling
    compact_interval_turns: int = 5
    reactive_interval_turns: int = 15

    # Directories
    transcripts_dir: Path = field(
        default_factory=lambda: TRANSCRIPTS_DIR
    )

    # Session
    session_id: str = ""

    def ensure_dirs(self) -> None:
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
