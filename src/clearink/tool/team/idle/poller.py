"""Idle-polling state machine for teammate autonomous task claiming.

The idle phase polls two sources in priority order:
  1. Inbox — only ``shutdown_request`` is handled directly; all other
     messages are written back for the WORK phase to process.
  2. Task board — ``scan_unclaimed_tasks()`` + ``claim_task()`` with
     file-level locking.

Design principle: the WORK phase *owns* inbox reading / clearing.
``idle_poll()`` only intercepts ``shutdown_request`` (system handler,
handled immediately).  Everything else flows through the inbox so
``_work_phase`` sees it through the normal code path.
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any

from .task_scanner import scan_unclaimed_tasks, claim_task


class PollResult(str, Enum):
    """Return value for :func:`idle_poll`.

    - ``SHUTDOWN`` — thread should exit.
    - ``WORK``    — work was written to inbox; re-enter WORK phase.
    """

    SHUTDOWN = "shutdown"
    WORK = "work"


# ── Constants ─────────────────────────────────────────────────

_DEFAULT_MAX_IDLE_SECONDS = 60
_POLL_INTERVAL_SECONDS = 2


# ── Lazy bus access (avoids circular imports at module load) ──

def _get_bus():
    from .. import lifecycle  # noqa: F811
    return lifecycle._bus


# ── Public API ────────────────────────────────────────────────

def idle_poll(
    name: str,
    role: str,
    stop_event: threading.Event,
    max_idle_time: int = _DEFAULT_MAX_IDLE_SECONDS,
) -> tuple[PollResult, list[dict[str, Any]]]:
    """Poll for new work during the IDLE phase.

    Priority order:
    1. **Inbox** — intercept ``shutdown_request`` (dispatch to
       system handler immediately, exits).  All other messages
       (plain content, non-shutdown protocol) are written back
       to the inbox so the WORK phase picks them up naturally.
    2. **Task board** — scan for unclaimed tasks whose
       dependencies are satisfied.  On a successful claim,
       a synthetic task message is written to the inbox and
       ``WORK`` is returned.
    3. **Idle notification** — ``send_idle_notification(name)``
       fires once per IDLE entry.
    4. **Sleep** — 2-second poll interval.

    After *max_idle_time* seconds without finding work the function
    returns ``SHUTDOWN`` (auto-shutdown).

    Args:
        name:          Teammate name.
        role:          Teammate role description (not currently
                       used inside the poller but passed for
                       future use / logging).
        stop_event:    ``threading.Event`` that signals external
                       shutdown (e.g. from ``stop_teammate``).
        max_idle_time: Seconds of continuous idleness before
                       auto-shutdown (default 60).

    Returns:
        ``(SHUTDOWN, [])``  — shutdown requested or timeout.
        ``(WORK,    [])``   — work was written to inbox; caller
                              should transition to WORK phase.
    """
    bus = _get_bus()

    idle_elapsed = 0
    idle_notified = False

    # Lazy import — only needed when a protocol message arrives
    handle_inbox_message = None
    send_idle_notification_fn = None

    while not stop_event.is_set() and idle_elapsed < max_idle_time:
        # ── Phase 1: Inbox check (shutdown only) ────────────
        raw_msgs = bus.read_and_clear(name)
        shutdown_found = False
        shutdown_msg = None
        messages_to_write_back: list[dict] = []

        for msg in raw_msgs:
            protocol = msg.get("protocol")
            if protocol and protocol.get("type") == "shutdown_request":
                shutdown_found = True
                shutdown_msg = msg
            else:
                messages_to_write_back.append(msg)

        # Write back non-shutdown messages BEFORE handling shutdown
        # (prevents message loss when shutdown arrives in a batch)
        for msg in messages_to_write_back:
            bus.write(name, msg)

        if shutdown_found and shutdown_msg is not None:
            # Lazy-import protocol dispatch only when needed
            if handle_inbox_message is None:
                from ..protocol import handle_inbox_message as _him
                handle_inbox_message = _him
            # System handler executes immediately, sets stop_event
            handle_inbox_message(name, shutdown_msg, [])
            if stop_event.is_set():
                return (PollResult.SHUTDOWN, [])

        if stop_event.is_set():
            return (PollResult.SHUTDOWN, [])

        # ── Phase 2: Task board check ───────────────────────
        unclaimed = scan_unclaimed_tasks()
        for task in unclaimed:
            task_id = task.get("id", "")
            claim_result = claim_task(task_id, owner=name)
            if not claim_result.startswith("Error:"):
                # Successfully claimed — write a synthetic task
                # message to the inbox for WORK to process
                subject = task.get("subject", task_id)
                description = task.get("description", "")
                task_content = f"[自领任务 #{task_id}]: {subject}"
                if description:
                    task_content += f"\n任务描述: {description}"
                task_content += (
                    "\n\n请完成此任务。完成后使用 complete_task "
                    f"工具将任务 #{task_id} 标记为完成。"
                )

                bus.write(name, {"from": "lead", "content": task_content})
                return (PollResult.WORK, [])

        # ── Phase 3: Idle notification (once per IDLE entry) ─
        if not idle_notified:
            if send_idle_notification_fn is None:
                from ..protocol import send_idle_notification as _sin
                send_idle_notification_fn = _sin
            send_idle_notification_fn(name)
            idle_notified = True

        # ── Phase 4: Sleep and count ────────────────────────
        time.sleep(_POLL_INTERVAL_SECONDS)
        idle_elapsed += _POLL_INTERVAL_SECONDS

    return (PollResult.SHUTDOWN, [])


def inject_identity_message(
    messages: list[dict[str, Any]],
    name: str,
    role: str,
) -> list[dict[str, Any]]:
    """Prepend an identity reminder if the first message lacks it.

    After ``compact_messages()`` trims or summarises conversation
    history the summary may not include the teammate's identity.
    While the system prompt (passed per API call) always carries
    identity, this is a conversational safeguard for long-running
    sessions where accumulated message history is compacted.

    If the first message already contains *name* the list is
    returned unmodified.

    Args:
        messages: The (possibly compacted) message history.
        name:     Teammate name.
        role:     Teammate role description.

    Returns:
        The message list, with an identity message prepended
        if needed.
    """
    if not messages:
        return messages

    first = messages[0]
    if isinstance(first, dict):
        content = first.get("content", "")
    else:
        content = str(first)

    # Check in string content and nested list content
    def _contains_name(c: Any) -> bool:
        if isinstance(c, str):
            return name in c
        if isinstance(c, list):
            return any(_contains_name(item) for item in c)
        return False

    if _contains_name(content):
        return messages

    identity_msg = {
        "role": "user",
        "content": f"[Identity: 你是 {name}, {role}. 请继续完成你的任务。]",
    }
    return [identity_msg] + messages
