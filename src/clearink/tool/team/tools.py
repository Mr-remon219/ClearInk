"""Registered tools for the teammate system.

All ``@register_tool`` decorators fire at import time, populating the
global ``TOOL`` and ``TOOL_HANDLERS`` registries in ``tool.register``.

Tools:
  spawn_teammate   — create a background teammate thread
  send_to_teammate — write a message to a teammate's inbox
  list_teammates   — list active teammates
  stop_teammate    — forcefully stop a teammate
  request_shutdown — graceful shutdown via protocol
  request_plan     — ask teammate to review a plan
  review_plan      — ask teammate to review content
"""

from __future__ import annotations

import threading

from clearink.hook import run_hooks
from ..register import register_tool
from .bus import _bus
from .lifecycle import (
    _active_teammates,
    _active_lock,
    _teammate_idle_loop,
)
from .protocol import make_protocol_request


# ── Basic teammate tools ──────────────────────────────────────

@register_tool(
    name="spawn_teammate",
    description="Spawn a teammate agent that runs in the background. "
                "The teammate has its own idle loop and can use tools (reduced set). "
                "Communicate with it via send_to_teammate.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Unique name for the teammate (e.g. 'analyst', 'searcher')",
            },
            "role": {
                "type": "string",
                "description": "Short role description (e.g. 'paper analyst', 'web searcher')",
            },
            "prompt": {
                "type": "string",
                "description": "Initial task for the teammate to work on",
            },
        },
        "required": ["name", "role", "prompt"],
    },
)
def spawn_teammate_thread(name: str, role: str, prompt: str) -> str:
    with _active_lock:
        if name in _active_teammates:
            return f"Error: teammate '{name}' already exists. Names must be unique."
        stop_event = threading.Event()
        _active_teammates[name] = stop_event

    thread = threading.Thread(
        target=_teammate_idle_loop,
        args=(name, role, prompt),
        daemon=True,
    )
    thread.start()

    run_hooks("teammate_spawned", {"name": name, "role": role})

    return (
        f"Teammate '{name}' ({role}) spawned and working on task.\n"
        f"Use send_to_teammate(name='{name}', message=...) to communicate. "
        f"The teammate will report results to your inbox automatically."
    )


@register_tool(
    name="send_to_teammate",
    description="Send a message/task to a teammate. "
                "The teammate will process it and report back to your inbox.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Teammate name to send the message to",
            },
            "message": {
                "type": "string",
                "description": "The message or task for the teammate",
            },
        },
        "required": ["name", "message"],
    },
)
def send_to_teammate(name: str, message: str) -> str:
    with _active_lock:
        active_names = list(_active_teammates)
        if name not in _active_teammates:
            return f"Error: no teammate named '{name}'. Active teammates: {active_names}"

    _bus.write(name, {"from": "lead", "content": message})
    return f"Message sent to teammate '{name}'."


@register_tool(
    name="list_teammates",
    description="List all active teammates.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def list_teammates() -> str:
    with _active_lock:
        active_names = list(_active_teammates)
    if not active_names:
        return "(no active teammates)"
    return "Active teammates:\n" + "\n".join(
        f"  - {name}" for name in active_names
    )


@register_tool(
    name="stop_teammate",
    description="Stop and remove a teammate by name.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Teammate name to stop"},
        },
        "required": ["name"],
    },
)
def stop_teammate(name: str) -> str:
    with _active_lock:
        stop_event = _active_teammates.pop(name, None)
    if stop_event is None:
        return f"Error: no teammate named '{name}'."
    stop_event.set()
    run_hooks("teammate_stopped", {"name": name})
    return f"Teammate '{name}' stopped."


# ── Protocol-based tools ──────────────────────────────────────

@register_tool(
    name="request_shutdown",
    description="Send a graceful shutdown request to a teammate via protocol. "
                "The teammate will acknowledge, clean up, and stop. "
                "The response arrives through the protocol matching system "
                "and appears in your inbox. For immediate forceful stop, "
                "use stop_teammate instead.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Teammate name to send shutdown request to",
            },
        },
        "required": ["name"],
    },
)
def request_shutdown(name: str) -> str:
    with _active_lock:
        if name not in _active_teammates:
            active_names = list(_active_teammates)
            return f"Error: no active teammate named '{name}'. Active teammates: {active_names}"
    request_id = make_protocol_request(name, "shutdown_request")
    return (
        f"Shutdown request sent to '{name}' (request_id: {request_id}). "
        f"The teammate will acknowledge and stop. "
        f"The response will appear in your inbox."
    )


@register_tool(
    name="request_plan",
    description="Request a teammate to review and approve/reject a plan. "
                "The teammate's LLM will process the plan and respond with "
                "its judgment. The response is matched via protocol.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Teammate name to send the plan to",
            },
            "plan": {
                "type": "string",
                "description": "The plan content for the teammate to review",
            },
        },
        "required": ["name", "plan"],
    },
)
def request_plan(name: str, plan: str) -> str:
    with _active_lock:
        if name not in _active_teammates:
            active_names = list(_active_teammates)
            return f"Error: no active teammate named '{name}'. Active teammates: {active_names}"
    request_id = make_protocol_request(name, "plan_request", {"plan": plan})
    return (
        f"Plan request sent to '{name}' (request_id: {request_id}). "
        f"The teammate will review and respond with approve/reject."
    )


@register_tool(
    name="review_plan",
    description="Request a teammate to review code, documents, or any content. "
                "The teammate's LLM will examine the content and provide "
                "detailed feedback. The response is matched via protocol.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Teammate name to send the review request to",
            },
            "content": {
                "type": "string",
                "description": "The content for the teammate to review",
            },
        },
        "required": ["name", "content"],
    },
)
def review_plan(name: str, content: str) -> str:
    with _active_lock:
        if name not in _active_teammates:
            active_names = list(_active_teammates)
            return f"Error: no active teammate named '{name}'. Active teammates: {active_names}"
    request_id = make_protocol_request(name, "review_request", {"content": content})
    return (
        f"Review request sent to '{name}' (request_id: {request_id}). "
        f"The teammate will review and provide feedback."
    )
