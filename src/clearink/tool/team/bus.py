"""Message bus for teammate communication.

A simple JSONL-based inbox system.  Each agent (lead, alice, bob, ...)
has its own ``{name}_inbox.jsonl`` file under ``data/team/``.

Messages are appended as JSON lines with an automatic ``timestamp``
field.  Reading is destructive: ``read_and_clear`` returns all messages
and truncates the file.  ``peek`` reads without clearing.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from clearink.config import TEAM_DIR


class MessageBus:
    """Thread-safe, file-backed message bus for agent communication.

    Each agent has a named inbox stored as ``data/team/{name}_inbox.jsonl``.
    The bus is protected by a re-entrant lock for in-process thread safety.
    """

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or TEAM_DIR
        self._lock = threading.RLock()

    def inbox_path(self, name: str) -> Path:
        return self.base_dir / f"{name}_inbox.jsonl"

    def write(self, name: str, message: dict) -> None:
        with self._lock:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            msg = dict(message)
            msg["timestamp"] = time.time()
            with open(self.inbox_path(name), "a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def read_and_clear(self, name: str) -> list[dict]:
        with self._lock:
            path = self.inbox_path(name)
            if not path.exists():
                return []
            try:
                lines = path.read_text(encoding="utf-8").strip().splitlines()
            except OSError:
                return []
            messages = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            path.write_text("", encoding="utf-8")
            return messages

    def peek(self, name: str) -> list[dict]:
        """Non-destructive read — returns messages without clearing the inbox."""
        with self._lock:
            path = self.inbox_path(name)
            if not path.exists():
                return []
            try:
                content = path.read_text(encoding="utf-8").strip()
            except OSError:
                return []
            if not content:
                return []
            messages = []
            for line in content.splitlines():
                if not line.strip():
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return messages


# Singleton instance
_bus = MessageBus()
