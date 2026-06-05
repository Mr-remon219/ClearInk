"""Protocol data model and global state for teammate communication.

Defines ProtocolState dataclass, the pending_requests registry, and
the response-type mapping used to validate request/response matching.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ProtocolState:
    """Tracks a single protocol request through its lifecycle.

    Fields:
        request_id: Unique monotonic ID like "req_004281".
        type:       Protocol type, e.g. "shutdown_request", "plan_request".
        sender:     Who initiated the request ("lead" or teammate name).
        target:     Who should receive / process the request.
        status:     "pending" | "approved" | "rejected".
        payload:    Free-form dict carrying protocol-specific data.
        created_at: Unix timestamp of creation.
        responded_at: Unix timestamp of response (None while pending).
    """

    request_id: str
    type: str
    sender: str
    target: str
    status: str          # pending | approved | rejected
    payload: dict        # plan text, shutdown reason, etc.
    created_at: float
    responded_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSONL bus transport."""
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProtocolState:
        """Deserialize from a dict received via JSONL bus.

        Only keys present in the dataclass fields are passed through,
        matching the pattern used by CronJob.from_dict in scheduler.py.
        """
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


# ── Global state ──────────────────────────────────────────────

pending_requests: dict[str, ProtocolState] = {}  # request_id → state
_request_lock = threading.RLock()
_request_counter: int = 0

# response_type → expected request_type
# Ensures a shutdown_response can only match a shutdown_request, etc.
_response_type_map: dict[str, str] = {
    "shutdown_response": "shutdown_request",
    "plan_response":     "plan_request",
    "review_response":   "review_request",
}

# protocol_type → (handler_kind, handler_fn)
# handler_kind: "system" (code executes directly, no LLM) or "llm" (inject into LLM)
_protocol_handlers: dict[str, tuple[str, object]] = {}

# Per-thread tracking — so a teammate thread knows it is responding
# to a protocol request and can wrap the LLM output in a protocol envelope.
_in_protocol_request: threading.local = threading.local()


# ── Thread-local helpers ──────────────────────────────────────

def get_active_protocol_request() -> dict[str, str] | None:
    """Return {request_id, protocol_type} if current thread is
    processing a protocol-triggered LLM turn, otherwise None."""
    return getattr(_in_protocol_request, "request", None)


def set_active_protocol_request(request_id: str, protocol_type: str) -> None:
    """Mark the current thread as processing a protocol request."""
    _in_protocol_request.request = {
        "request_id": request_id,
        "protocol_type": protocol_type,
    }


def clear_protocol_request() -> None:
    """Clear the thread-local protocol tracking."""
    try:
        del _in_protocol_request.request
    except AttributeError:
        pass
