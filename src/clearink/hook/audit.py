"""Built-in audit-log hook — JSONL event trace for the entire system.

Imported for side effects: registers a low-priority handler on every
hook type that appends a structured JSON line to
``data/logs/audit.jsonl``.

This is the "catch-all" safety net — any hook event that fires is
automatically logged, even if no other hook handler is registered.
"""

from __future__ import annotations

import json
import time

from clearink.config import LOGS_DIR
from .hook import HOOKS, register_hook

_AUDIT_PATH = LOGS_DIR / "audit.jsonl"


def _audit_handler(context: dict) -> None:
    """Log a single hook event as one JSON line."""
    # Determine which hook type triggered this call via the context
    hook_type = context.get("_hook_type", "unknown")
    entry = {
        "ts": time.time(),
        "hook": hook_type,
        "data": {
            k: v for k, v in context.items()
            if not k.startswith("_") and k not in ("messages", "hook_context")
        },
    }
    # Serialize hook_context specially — only keep summary fields
    hc = context.get("hook_context", {})
    if hc:
        entry["data"]["hc"] = {
            "paper": (
                hc.get("current_paper", {}).get("name")
                if isinstance(hc.get("current_paper"), dict) else None
            ),
            "papers_count": len(hc.get("papers_accessed", [])),
            "citation": hc.get("citation_requested", False),
        }

    _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


# Register on every hook type with lowest priority (runs last)
for _hook_type in HOOKS:
    register_hook(_hook_type, name="audit_log", priority=999)(_audit_handler)
