from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

_CLEARINK_DIR = Path(__file__).resolve().parents[3] / "data"


@dataclass
class CompactConfig:
    # L3: Tool Result Archiving
    l3_min_chars: int = 4000

    # L1: Middle Trimming
    l1_keep_first_exchanges: int = 3
    l1_keep_last_exchanges: int = 5
    l1_min_exchanges: int = 4

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
    task_outputs_dir: Path = field(
        default_factory=lambda: _CLEARINK_DIR / "task_outputs"
    )
    transcripts_dir: Path = field(
        default_factory=lambda: _CLEARINK_DIR / ".transcripts"
    )

    # Session
    session_id: str = ""

    def ensure_dirs(self) -> None:
        self.task_outputs_dir.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
