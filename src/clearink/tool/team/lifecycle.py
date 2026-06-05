"""Teammate lifecycle management: spawn, stop, idle loop state machine.

The idle loop is a three-state machine (WORK → IDLE → SHUTDOWN) that
processes inbox messages, runs LLM turns, and polls for autonomous work
via the task board.
"""

from __future__ import annotations

import os
import threading

from anthropic import Anthropic
from dotenv import load_dotenv

from ...config import ENV_PATH
from ...message import content_block_to_dict
from .bus import _bus
from .protocol import (
    handle_inbox_message,
    get_active_protocol_request,
    clear_protocol_request,
    consume_lead_inbox,
)
from .idle import PollResult, idle_poll
from . import tools as _tools  # noqa: F401 — ensure tools are registered

load_dotenv(ENV_PATH, override=True)

_SUB_MODEL = os.getenv("SUBAGENT_MODEL", "deepseek-v4-flash")

# Tools excluded from teammate agent's tool set
_EXCLUDED_TOOLS = {
    "spawn_teammate", "schedule_cron", "cancel_scheduled_job",
    "request_shutdown", "request_plan", "review_plan",
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
    client = Anthropic()
    tools, handlers = _get_teammate_tools()
    collected: list[str] = []

    for _ in range(max_turns):
        try:
            response = client.messages.create(
                model=_SUB_MODEL,
                system=f"You are {name}, a specialized AI teammate. "
                       f"Role: {role}. "
                       f"Work on the assigned task and report back when done. "
                       f"Be concise and focused.",
                messages=messages,
                tools=tools,
                max_tokens=2048,
                thinking={"type": "disabled"},
            )
        except Exception as e:
            return f"[Teammate {name} error: {e}]"

        if response.stop_reason == "end_turn":
            text = "".join(
                b.text for b in response.content if b.type == "text"
            )
            collected.append(text)
            return "\n".join(filter(None, collected)) or f"[Teammate {name}: no output]"

        for block in response.content:
            if block.type == "text":
                text = block.text or ""
                collected.append(text)
                messages.append({"role": "assistant", "content": text})
            elif block.type == "tool_use":
                handler = handlers.get(block.name)
                try:
                    result = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    result = f"Error: {e}"
                messages.append({"role": "assistant", "content": [content_block_to_dict(block)]})
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    }],
                })

    return "\n".join(filter(None, collected)) + "\n\n[teammate: max turns reached]" if collected else f"[Teammate {name}: max turns reached]"


# ── Idle loop (WORK / IDLE / SHUTDOWN state machine) ─────────

def _teammate_idle_loop(name: str, role: str, prompt: str) -> None:
    """Three-state main loop for a teammate background thread.

    WORK phase : read inbox messages, run LLM turns, write responses.
    IDLE phase : poll inbox (for shutdown) and task board; auto-claim.
    SHUTDOWN   : write final summary and exit.

    Transitions:
        WORK ──(inbox empty)──> IDLE ──(task claimed)──> WORK
          │                       │
          └──(shutdown/stop)──────┴──(60s idle)────────> SHUTDOWN
    """
    with _active_lock:
        stop_event = _active_teammates.get(name)
    if stop_event is None:
        return

    # Write initial task as first inbox message
    _bus.write(name, {"from": "lead", "content": prompt})

    state = "WORK"  # WORK | IDLE | SHUTDOWN

    while not stop_event.is_set() and state != "SHUTDOWN":
        if state == "WORK":
            state = _work_phase(name, role, stop_event)
        elif state == "IDLE":
            state = _idle_phase(name, role, stop_event)

    # Final shutdown notification to lead
    _bus.write("lead", {
        "from": name,
        "content": f"[{name}] 已完成所有任务，进入关闭状态。",
    })


def _work_phase(name: str, role: str, stop_event: threading.Event) -> str:
    """Process all available inbox messages.  Returns next state.

    Returns:
        ``"IDLE"``     — inbox is empty, no more work.
        ``"SHUTDOWN"`` — stop_event was set.
    """
    while not stop_event.is_set():
        raw_msgs = _bus.read_and_clear(name)

        if not raw_msgs:
            return "IDLE"

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
            return "SHUTDOWN"

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
            return "SHUTDOWN"

        continue

    return "SHUTDOWN"


def _idle_phase(name: str, role: str, stop_event: threading.Event) -> str:
    """Poll for new work via :func:`idle_poll`.  Returns next state."""
    result, _ = idle_poll(name, role, stop_event)
    if result == PollResult.WORK:
        return "WORK"
    return "SHUTDOWN"


# ── Lead inbox collection ─────────────────────────────────────

def collect_teammate_messages() -> list[dict]:
    """Collect and format teammate messages for LLM consumption.

    Delegates to consume_lead_inbox() which:
    - Intercepts protocol responses and matches them to pending requests
    - Formats idle notifications as human-readable status lines
    - Passes through plain content messages (backward compatible)
    """
    return consume_lead_inbox(route_protocol=True)
