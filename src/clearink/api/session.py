"""Session management for the ClearInk API layer.

Provides in-memory session storage suitable for single-process
deployments.  Replace ``SessionManager`` with a Redis / DB backend
when scaling to multiple workers.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field



@dataclass
class Session:
    """Per-user state for a ClearInk conversation.

    Attributes:
        session_id:   Unique identifier (UUID4 hex).
        messages:     The full ``agent_loop`` message history.
        mode:         ``1`` (formula analysis) or ``2`` (paper Q&A).
        step_mode:    Whether step-by-step output is enabled.
        created_at:   Unix timestamp of creation.
        last_access:  Unix timestamp of last API call.
    """

    session_id: str
    messages: list[dict]
    mode: int = 1
    step_mode: bool = False
    step_number: int = 0
    paper_tasks: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        repr=False,
        compare=False,
    )

    def reset(
        self,
        messages: list[dict],
        *,
        mode: int = 1,
        step_mode: bool = False,
    ) -> None:
        """Reset conversation state while keeping the session identity."""
        now = time.time()
        with self.lock:
            self.messages = messages
            self.mode = mode
            self.step_mode = step_mode
            self.step_number = 0
            self.paper_tasks = []
            self.created_at = now
            self.last_access = now


class SessionManager:
    """Thread-safe in-memory session store.

    Usage::

        mgr = SessionManager()
        sess = mgr.create()                 # new session
        sess = mgr.get_or_create("abc123")  # retrieve existing or create
        mgr.touch("abc123")                # bump last_access
        mgr.delete("abc123")               # remove
        expired = mgr.cleanup(3600)         # remove sessions older than 1h
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()

    # ── CRUD ────────────────────────────────────────────────

    def create(self, session_id: str | None = None) -> Session:
        """Create a new session with an empty message list.

        Args:
            session_id: Optional pre-defined ID.  A UUID4 hex is
                        generated if omitted.

        Returns:
            The new ``Session`` object.
        """
        sid = session_id or uuid.uuid4().hex[:16]
        session = Session(session_id=sid, messages=[])
        with self._lock:
            self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Return the session for *session_id*, or ``None``."""
        with self._lock:
            return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> Session:
        """Return existing session or create a new one with the given id."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = Session(session_id=session_id, messages=[])
                self._sessions[session_id] = session

        return session

    def delete(self, session_id: str) -> None:
        """Remove a session.  No-op if it does not exist."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def touch(self, session_id: str) -> None:
        """Update ``last_access`` to the current time."""
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess is not None:
                sess.last_access = time.time()

    def cleanup(self, max_age: float = 3600) -> int:
        """Remove sessions that haven't been accessed for *max_age* seconds.

        Args:
            max_age: Maximum idle time in seconds (default 1 hour).

        Returns:
            Number of sessions removed.
        """
        now = time.time()
        removed = 0
        with self._lock:
            stale = [
                sid for sid, s in self._sessions.items()
                if now - s.last_access > max_age
            ]
            for sid in stale:
                del self._sessions[sid]
                removed += 1
        return removed


# ── Module-level singleton ─────────────────────────────────

_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """Return the module-level ``SessionManager`` singleton."""
    return _session_manager
