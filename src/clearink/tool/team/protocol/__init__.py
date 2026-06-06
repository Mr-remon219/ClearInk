"""Teammate protocol layer — structured request/response communication.

Key exports:
  ProtocolState           — dataclass tracking one request lifecycle
  pending_requests        — global registry: request_id → ProtocolState
  make_protocol_request() — send a structured request to a teammate
  match_response()        — validate & update a pending request with a response
  handle_inbox_message()  — receiver-side dispatch (system / llm handlers)
  consume_lead_inbox()    — unified lead inbox reader + protocol router
  register_protocol()     — register a request/response type pair
  register_protocol_handler() — register a handler for a protocol type
  get_active_protocol_request() — thread-local: check if processing protocol
  clear_protocol_request()      — thread-local: clear protocol tracking
"""

from .state import (
    ProtocolState,
    pending_requests,
    get_active_protocol_request,
    set_active_protocol_request,
    clear_protocol_request,
)

from .protocol import (
    generate_request_id,
    register_protocol,
    register_protocol_handler,
    make_protocol_request,
    match_response,
    handle_inbox_message,
    consume_lead_inbox,
)

# Ensure built-in handlers are registered
from . import handlers  # noqa: F401 — triggers _register_default_protocols()

__all__ = [
    "ProtocolState",
    "pending_requests",
    "get_active_protocol_request",
    "set_active_protocol_request",
    "clear_protocol_request",
    "generate_request_id",
    "register_protocol",
    "register_protocol_handler",
    "make_protocol_request",
    "match_response",
    "handle_inbox_message",
    "consume_lead_inbox",
]
