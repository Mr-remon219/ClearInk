"""Teammate lifecycle management: spawn, stop, simplified state machine.

The lifecycle is a two-phase model (WORK → LINGER → EXIT) that
processes inbox messages, runs LLM turns, and exits after a configurable
idle timeout.  No auto-claiming or task-board polling — all work is
explicitly assigned.
"""

from __future__ import annotations

import os
import threading
import time

from anthropic import Anthropic
from dotenv import load_dotenv

from ...config import ENV_PATH
from .bus import _bus
from .protocol import (
    handle_inbox_message,
    get_active_protocol_request,
    clear_protocol_request,
    consume_lead_inbox,
)
from . import tools as _tools  # noqa: F401 — ensure tools are registered

load_dotenv(ENV_PATH, override=True)

_SUB_MODEL = os.getenv("SUBAGENT_MODEL", "deepseek-v4-flash")

# Configurable linger timeout (seconds) before an idle teammate exits
_LINGER_MAX_SECONDS = int(os.getenv("TEAMMATE_LINGER_SECONDS", "10"))
_LINGER_POLL_SECONDS = 1

# Tools excluded from teammate agent's tool set.
# spawn_subagent is intentionally NOT excluded — teammates can use it to accelerate sub-tasks.
# subagent internally blocks recursive spawn_subagent calls.
_EXCLUDED_TOOLS = {
    "spawn_teammate",
    "request_shutdown",
    # Regulation / dispatch tools — teammates cannot supervise or dispatch
    "execute_parallel", "auto_dispatch",
    "regulate_teammates", "inspect_teammate",
    "reject_and_reassign", "audit_stranded_tasks",
}

# Active teammate registry
_active_teammates: dict[str, threading.Event] = {}  # name → stop_event
_active_lock = threading.RLock()


# ── Tool filtering ────────────────────────────────────────────

def _get_teammate_tools() -> tuple[list[dict], dict]:
    """Return (tool_defs, handler_map) filtered by _EXCLUDED_TOOLS."""
    from ..register import TOOL, TOOL_HANDLERS  # lazy to avoid circular deps

    tools = [t for t in TOOL if t["name"] not in _EXCLUDED_TOOLS]
    handlers = {
        k: v for k, v in TOOL_HANDLERS.items()
        if k not in _EXCLUDED_TOOLS
    }
    return tools, handlers


# ── Teammate LLM turn ─────────────────────────────────────────

def _run_teammate_turn(
    name: str,
    role: str,
    messages: list[dict],
    max_turns: int = 5,
) -> str:
    """Run up to *max_turns* LLM calls for a single work batch."""
    from .._llm_loop import run_llm_tool_loop

    tools, handlers = _get_teammate_tools()
    system = (
        f"You are {name}, a specialized AI teammate. "
        f"Role: {role}. "
        f"Work on the assigned task and report back when done. "
        f"Be concise and focused. "
        f"If your task involves multiple independent sub-steps "
        f"(e.g., looking up multiple papers, verifying multiple "
        f"citations), use spawn_subagent to execute them in "
        f"parallel. Each subagent runs independently with its "
        f"own tool set. Collect their results and synthesize a "
        f"single response."
    )

    try:
        return run_llm_tool_loop(
            client=Anthropic(),
            model=_SUB_MODEL,
            system=system,
            messages=messages,
            tools=tools,
            handlers=handlers,
            max_turns=max_turns,
        )
    except Exception as e:
        return f"[Teammate {name} error: {e}]"


# ── Simplified lifecycle (WORK → LINGER → EXIT) ───────────────

def _teammate_idle_loop(name: str, role: str, prompt: str) -> None:
    """Two-phase main loop for a teammate background thread.

    WORK   — read inbox, run LLM turns, write responses to lead.
    LINGER — inbox empty; wait for new messages, exit on timeout.
    EXIT   — final cleanup, notify lead.

    No idle polling, no auto-claiming — all work explicitly assigned.
    """
    with _active_lock:
        stop_event = _active_teammates.get(name)
    if stop_event is None:
        return

    # Write initial task as first inbox message (skip if prompt is empty —
    # the task will be written later via assign_task_to_teammate)
    if prompt:
        _bus.write(name, {"from": "lead", "content": prompt})

    while not stop_event.is_set():
        # ── WORK: process all available inbox messages ──
        shutdown = _work_phase(name, role, stop_event)
        if shutdown:
            break

        # ── LINGER: wait for new assignments, exit on timeout ──
        found_work = False
        for _ in range(_LINGER_MAX_SECONDS):
            if stop_event.is_set():
                break
            time.sleep(_LINGER_POLL_SECONDS)

            if _bus.peek(name):
                found_work = True
                break  # re-enter WORK — _work_phase will read_and_clear

        if not found_work and not stop_event.is_set():
            break  # timeout → EXIT

    # Clean up registry before exit
    with _active_lock:
        _active_teammates.pop(name, None)

    # Final shutdown notification to lead
    _bus.write("lead", {
        "from": name,
        "content": f"[{name}] 已完成所有任务，进入关闭状态。",
    })


def _work_phase(name: str, role: str, stop_event: threading.Event) -> bool:
    """Process all available inbox messages.

    Returns True if shutdown was requested (caller should exit),
    False if inbox is empty (caller should enter LINGER).
    """
    while not stop_event.is_set():
        raw_msgs = _bus.read_and_clear(name)

        if not raw_msgs:
            return False  # inbox empty → LINGER

        llm_messages: list[dict] = []

        for msg in raw_msgs:
            if msg.get("protocol"):
                handle_inbox_message(name, msg, llm_messages)
            else:
                sender = msg.get("from", "unknown")
                content = msg.get("content", "")
                llm_messages.append({
                    "role": "user",
                    "content": f"[{sender}]: {content}",
                })

        if stop_event.is_set():
            return True

        if llm_messages:
            result = _run_teammate_turn(name, role, llm_messages)

            active_req = get_active_protocol_request()
            if active_req:
                response_type = active_req["protocol_type"].replace(
                    "_request", "_response"
                )
                _bus.write("lead", {
                    "from": name,
                    "content": result,
                    "protocol": {
                        "type": response_type,
                        "request_id": active_req["request_id"],
                        "payload": {
                            "result": result,
                            "approve": not result.strip().lower().startswith(
                                "reject"
                            ),
                        },
                    },
                })
                clear_protocol_request()
            else:
                _bus.write("lead", {
                    "from": name,
                    "content": result,
                })

        if stop_event.is_set():
            return True

    return True


# ── Lead inbox collection ─────────────────────────────────────

def collect_teammate_messages() -> list[dict]:
    """Collect and format teammate messages for LLM consumption.

    Delegates to consume_lead_inbox() which intercepts protocol responses,
    matches them to pending requests, and formats them as human-readable
    status lines.
    """
    return consume_lead_inbox(route_protocol=True)
