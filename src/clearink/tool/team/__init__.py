"""Teammate system — unified package.

Communication protocol, idle polling + task claiming, git worktree
management, and the teammate lifecycle (spawn / work / idle / shutdown).

Importing this package triggers all ``@register_tool`` registrations
so the LLM can discover teammate-related tools automatically.

Public API:
  ``collect_teammate_messages()`` — called from main agent loop
  ``_active_teammates``, ``_active_lock`` — accessed by protocol handlers
"""

# ── Trigger tool registrations (side-effect imports) ──────────
from . import tools as tools              # 7 tools (spawn, send, list, stop, request_*)
from .worktree import worktree as worktree   # 4 tools (create/remove/keep/bind worktree)

# ── Public API ────────────────────────────────────────────────
from .bus import MessageBus as MessageBus, _bus as _bus
from .lifecycle import (
    collect_teammate_messages as collect_teammate_messages,
    _active_teammates as _active_teammates,
    _active_lock as _active_lock,
    _teammate_idle_loop as _teammate_idle_loop,
    _work_phase as _work_phase,
    _idle_phase as _idle_phase,
)

from .protocol import (  # noqa: F401 — re-export for external consumers
    ProtocolState,
    pending_requests,
    handle_inbox_message,
    send_idle_notification,
    get_active_protocol_request,
    clear_protocol_request,
    make_protocol_request,
    match_response,
    consume_lead_inbox,
    register_protocol,
    register_protocol_handler,
)

from .idle import (  # noqa: F401
    PollResult,
    idle_poll,
    inject_identity_message,
    scan_unclaimed_tasks,
    claim_task,
)

from .worktree import (  # noqa: F401
    create_worktree,
    remove_worktree,
    keep_worktree,
    bind_task_to_worktree,
    log_event,
    run_git,
    validate_worktree_name,
)
