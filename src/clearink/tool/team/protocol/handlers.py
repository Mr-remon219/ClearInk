"""Built-in protocol handlers for the teammate communication layer.

Handlers come in two flavours:
- "system"  — executed directly in code (e.g. shutdown sets stop_event).
- "llm"     — injects a formatted message into the teammate's LLM context,
              letting the AI teammate process the request naturally.

Registered via register_protocol_handler() at module load.

Currently only shutdown_request is supported — plan/review were removed
in favour of the Regulation module's inspect_teammate + reject_and_reassign.
"""

from __future__ import annotations

from typing import Any

from .protocol import register_protocol, register_protocol_handler


# ── Lazy access to teammate internals ──────────────────────────
# Avoided at module top level to prevent circular imports at init time.


def _get_teammate_state(name: str):
    """Return (stop_event, active_teammates, active_lock) for a teammate."""
    from .. import lifecycle  # noqa: F811
    return (
        lifecycle._active_teammates.get(name),
        lifecycle._active_teammates,
        lifecycle._active_lock,
    )


# ── System handlers ────────────────────────────────────────────


def _handle_shutdown_request(teammate_name: str, protocol: dict[str, Any]) -> dict[str, Any] | None:
    """Handle a shutdown_request on the teammate side.

    Sets the stop_event so the idle loop exits cleanly.  Writes a
    shutdown_response back to the lead's inbox.
    """
    request_id = protocol.get("request_id", "")

    stop_event, active_teammates, active_lock = _get_teammate_state(teammate_name)

    if stop_event is None:
        # Teammate already stopped or never existed
        return {
            "from": teammate_name,
            "content": "",
            "protocol": {
                "type": "shutdown_response",
                "request_id": request_id,
                "payload": {
                    "approve": True,
                    "result": f"{teammate_name} already stopped",
                },
            },
        }

    # Signal the thread to stop and remove from registry
    with active_lock:
        active_teammates.pop(teammate_name, None)
    stop_event.set()

    return {
        "from": teammate_name,
        "content": "",
        "protocol": {
            "type": "shutdown_response",
            "request_id": request_id,
            "payload": {
                "approve": True,
                "result": f"{teammate_name} 已确认关机",
            },
        },
    }


# ── Auto-registration ──────────────────────────────────────────

def _register_default_protocols() -> None:
    """Called at module load to register all built-in protocols."""
    register_protocol("shutdown_request", "shutdown_response")

    register_protocol_handler("shutdown_request", "system", _handle_shutdown_request)


_register_default_protocols()
