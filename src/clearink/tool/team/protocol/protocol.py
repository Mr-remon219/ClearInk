"""Core protocol functions for the teammate communication layer.

Provides:
- Request generation (make_protocol_request)
- Response matching with type-safety validation (match_response)
- Inbound message dispatch on the receiver side (handle_inbox_message)
- Unified lead inbox consumption (consume_lead_inbox)
- Protocol registration API (register_protocol, register_protocol_handler)
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from .state import (
    ProtocolState,
    pending_requests,
    _request_lock,
    _request_counter,
    _response_type_map,
    _protocol_handlers,
    set_active_protocol_request,
)

_PROCESS_STARTED_AT = time.time()


# ── ID generation ─────────────────────────────────────────────

def generate_request_id() -> str:
    """Return a thread-safe sequential request ID: req_000001, req_000002, ..."""
    global _request_counter
    with _request_lock:
        _request_counter += 1
        return f"req_{_request_counter:06d}"


# ── Protocol registration API ─────────────────────────────────

def register_protocol(request_type: str, response_type: str) -> None:
    """Register a request/response type pair for type-safety validation.

    When a response arrives, match_response() looks up the response type
    in _response_type_map to verify it corresponds to the expected request.

    Example:
        register_protocol("deploy_request", "deploy_response")
    """
    _response_type_map[response_type] = request_type


def register_protocol_handler(
    protocol_type: str,
    handler_kind: str,
    handler_fn: Callable[..., Any],
) -> None:
    """Register a handler for inbound protocol messages on the receiver side.

    Args:
        protocol_type: The protocol message type (e.g. "shutdown_request").
        handler_kind: "system" (handled in code, no LLM) or "llm"
                      (injected into the LLM context for processing).
        handler_fn: For "system": fn(teammate_name, protocol) -> response_dict.
                    For "llm": fn(teammate_name, protocol) -> user_message_dict.
    """
    _protocol_handlers[protocol_type] = (handler_kind, handler_fn)


# ── BUS access (lazy import to avoid circular deps) ───────────

def _get_bus():
    """Lazy-load the singleton MessageBus from lifecycle.py."""
    from .. import lifecycle  # noqa: F811
    return lifecycle._bus


# ── Sender-side: create a protocol request ─────────────────────

def make_protocol_request(
    target: str,
    request_type: str,
    payload: dict[str, Any] | None = None,
) -> str:
    """Create a protocol request, store state, write to target's inbox.

    Called by the lead (or any initiating agent) to send a structured
    request to a teammate through the message bus.

    Args:
        target:       Inbox name of the receiver (teammate name).
        request_type: e.g. "shutdown_request", "plan_request".
        payload:      Arbitrary protocol-specific data.

    Returns:
        The generated request_id string for tracking.
    """
    request_id = generate_request_id()
    state = ProtocolState(
        request_id=request_id,
        type=request_type,
        sender="lead",
        target=target,
        status="pending",
        payload=payload or {},
        created_at=time.time(),
    )

    with _request_lock:
        pending_requests[request_id] = state

    bus = _get_bus()
    bus.write(target, {
        "from": "lead",
        "content": "",
        "protocol": {
            "type": request_type,
            "request_id": request_id,
            "payload": payload or {},
        },
    })

    return request_id


# ── Sender-side: match inbound response to pending request ─────

def match_response(
    response_type: str,
    request_id: str,
    approve: bool,
) -> ProtocolState | None:
    """Match an inbound protocol response to its original pending request.

    Validates that the response type corresponds to the original request type
    (e.g. shutdown_response → shutdown_request), then updates the state.

    Args:
        response_type: e.g. "shutdown_response", "plan_response".
        request_id:    The request ID from the pending request.
        approve:       True → status "approved", False → "rejected".

    Returns:
        Updated ProtocolState, or None if no match / type mismatch.
    """
    expected_request_type = _response_type_map.get(response_type)
    if expected_request_type is None:
        return None  # Unknown response type

    with _request_lock:
        state = pending_requests.get(request_id)
        if state is None:
            return None  # No such pending request

        # Type-safety: verify the response matches the original request type
        if state.type != expected_request_type:
            return None

        state.status = "approved" if approve else "rejected"
        state.responded_at = time.time()

    return state


# ── Receiver-side: dispatch inbound messages ───────────────────

def handle_inbox_message(
    name: str,
    msg: dict[str, Any],
    messages: list[dict[str, Any]],
) -> bool:
    """Process a single inbound message for teammate *name*.

    Dispatches protocol messages to their registered handler and
    appends plain content messages directly to the LLM message list.

    Args:
        name:     The receiving teammate's name.
        msg:      A raw message dict read from the inbox.
        messages: The list of LLM-formatted messages to extend.

    Returns:
        True if at least one message was added to *messages*
        (caller should run an LLM turn), False if the message
        was fully handled in code (e.g. system handler).
    """
    protocol = msg.get("protocol")
    if not protocol:
        # Plain content message → forward to LLM
        sender = msg.get("from", "unknown")
        content = msg.get("content", "")
        messages.append({
            "role": "user",
            "content": f"[{sender}]: {content}",
        })
        return True

    # Protocol message → dispatch to registered handler
    protocol_type = protocol.get("type", "")
    handler_entry = _protocol_handlers.get(protocol_type)

    if handler_entry is None:
        # Unknown protocol type → pass through as plain content
        messages.append({
            "role": "user",
            "content": json.dumps(protocol, ensure_ascii=False),
        })
        return True

    handler_kind, handler_fn = handler_entry

    if handler_kind == "system":
        # System handler: execute immediately, write response to lead inbox
        response = handler_fn(name, protocol)
        if response:
            bus = _get_bus()
            bus.write("lead", response)
        return False  # No LLM turn needed

    elif handler_kind == "llm":
        # LLM handler: inject formatted message for LLM to process
        user_msg = handler_fn(name, protocol)
        if user_msg:
            messages.append(user_msg)
            set_active_protocol_request(
                protocol.get("request_id", ""),
                protocol_type,
            )
        return True

    return False


# ── Lead inbox consumption ────────────────────────────────────

def consume_lead_inbox(route_protocol: bool = True) -> list[dict[str, Any]]:
    """Read and consume all messages from the lead's inbox.

    Separates protocol-level messages from plain content.  Protocol
    responses are matched to pending_requests via match_response();
    the result is formatted as a human-readable summary so the LLM
    never sees raw protocol metadata.

    Content messages without a protocol key are passed through as
    [Teammate <name>]: <content> for backward compatibility.

    Args:
        route_protocol: When True, protocol messages are intercepted
                        and matched in code.  When False, all messages
                        are treated as plain content.

    Returns:
        A list of message dicts ready for injection into the LLM context.
    """
    bus = _get_bus()
    raw_msgs = bus.read_and_clear("lead")
    result: list[dict[str, Any]] = []

    for msg in raw_msgs:
        timestamp = msg.get("timestamp")
        if isinstance(timestamp, int | float) and timestamp < _PROCESS_STARTED_AT:
            continue

        protocol = msg.get("protocol") if route_protocol else None
        sender = msg.get("from", "unknown")

        if protocol:
            ptype = protocol.get("type", "")
            req_id = protocol.get("request_id", "")
            payload = protocol.get("payload", {})

            if ptype in _response_type_map:
                approved = payload.get("approve", True)
                matched = match_response(ptype, req_id, approved)
                if matched:
                    status_label = "已批准" if matched.status == "approved" else "已拒绝"
                    req_label = matched.type.replace("_request", "")
                    result.append({
                        "role": "user",
                        "content": (
                            f"✅ [Teammate {sender}]: {req_label} {status_label}"
                            f"{' — ' + payload.get('result', '') if payload.get('result') else ''}"
                        ),
                    })
                else:
                    # Response didn't match any pending request
                    result.append({
                        "role": "user",
                        "content": f"⚠️ [Teammate {sender}]: 收到未匹配的协议响应 ({ptype}, {req_id})",
                    })

            else:
                # Unknown protocol type → pass through with minimal formatting
                result.append({
                    "role": "user",
                    "content": (
                        f"[Teammate {sender}]: [protocol:{ptype}] "
                        f"{json.dumps(payload, ensure_ascii=False)}"
                    ),
                })

        else:
            # Plain content message (backward compatible)
            content = msg.get("content", "")
            result.append({
                "role": "user",
                "content": f"[Teammate {sender}]: {content}",
            })

    return result
