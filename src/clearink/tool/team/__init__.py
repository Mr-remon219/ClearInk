"""Teammate system — unified package.

Communication protocol, teammate lifecycle (spawn → work → linger → exit),
and execution tracking.

Importing this package triggers all ``@register_tool`` registrations
so the LLM can discover teammate-related tools automatically.

Public API:
  ``collect_teammate_messages()`` — called from main agent loop
  ``_active_teammates``, ``_active_lock`` — accessed by protocol handlers
  ``tracker`` — ExecutionTracker singleton
"""

# ── Trigger tool registrations (side-effect imports) ──────────
from . import tools as tools  # teammate tools

# ── Public API ────────────────────────────────────────────────
from .bus import MessageBus as MessageBus, _bus as _bus
from .tracker import tracker as tracker
from .lifecycle import (
    collect_teammate_messages as collect_teammate_messages,
    _active_teammates as _active_teammates,
    _active_lock as _active_lock,
    _teammate_idle_loop as _teammate_idle_loop,
    _work_phase as _work_phase,
)

from .protocol import (  # noqa: F401 — re-export for external consumers
    ProtocolState,
    pending_requests,
    handle_inbox_message,
    get_active_protocol_request,
    clear_protocol_request,
    make_protocol_request,
    match_response,
    consume_lead_inbox,
    register_protocol,
    register_protocol_handler,
)
