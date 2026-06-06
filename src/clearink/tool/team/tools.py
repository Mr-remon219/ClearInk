"""Registered tools for the teammate system.

All ``@register_tool`` decorators fire at import time, populating the
global ``TOOL`` and ``TOOL_HANDLERS`` registries in ``tool.register``.

Tools:
  spawn_teammate          — create a background teammate thread
  assign_task_to_teammate — explicitly assign a task to a teammate
  execute_parallel        — spawn teammates for multiple tasks at once
  send_to_teammate        — write a message to a teammate's inbox
  list_teammates          — list active teammates
  stop_teammate           — forcefully stop a teammate
  request_shutdown        — graceful shutdown via protocol
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

# Batch counter for execute_parallel to prevent name collisions across calls
_parallel_batch_counter = 0
_counter_lock = threading.Lock()


# ── Basic teammate tools ──────────────────────────────────────

@register_tool(
    name="spawn_teammate",
    description="Spawn a teammate agent that runs in the background. "
                "The teammate processes assigned tasks from its inbox. "
                "Communicate with it via send_to_teammate or assign_task_to_teammate.",
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
    name="assign_task_to_teammate",
    description="Explicitly assign a task to a specific teammate. "
                "Claims the task via TaskManager, writes task details to teammate's inbox. "
                "Use this after spawn_teammate to direct work to a specific teammate.",
    input_schema={
        "type": "object",
        "properties": {
            "teammate_name": {
                "type": "string",
                "description": "Name of the teammate to assign the task to",
            },
            "task_id": {
                "type": "string",
                "description": "Task ID to assign",
            },
        },
        "required": ["teammate_name", "task_id"],
    },
)
def assign_task_to_teammate(teammate_name: str, task_id: str) -> str:
    """Explicitly assign a task to a specific teammate.

    If the task is already claimed by the same teammate (e.g. by
    execute_parallel which claims before spawning), skips the claim
    and proceeds directly to inbox write + tracker update.
    """
    # 1. Validate teammate exists
    with _active_lock:
        if teammate_name not in _active_teammates:
            return f"Error: no teammate named '{teammate_name}'."

    # 2. Claim the task via TaskManager (skip if already owned by this teammate)
    from ..task_system.manager import _manager
    claim_result = _manager.claim_task(task_id, owner=teammate_name)
    if claim_result.startswith("Error:"):
        # Check if already claimed by the same teammate — if so, proceed
        task_check = _manager.list_tasks.get(task_id)
        if not (task_check and task_check.get("owner") == teammate_name):
            return claim_result

    # 3. Get task details
    task = _manager.list_tasks.get(task_id)
    if task is None:
        return f"Error: task '{task_id}' not found."

    # 4. Write task message to teammate's inbox
    task_msg = (
        f"[Assigned Task #{task_id}]: {task['subject']}\n"
        f"Description: {task.get('description', 'N/A')}\n\n"
        f"Complete this task and report back. "
        f"Use complete_task when done."
    )
    _bus.write(teammate_name, {"from": "lead", "content": task_msg})

    # 5. Record to ExecutionTracker
    from .tracker import tracker
    tracker.record_assignment(teammate_name, task_id)

    # 6. Fire hook for DAG lifecycle tracking
    from clearink.hook import run_hooks as _run_hooks
    _run_hooks("task_lifecycle", {
        "event": "reassigned", "task_id": task_id,
        "to_teammate": teammate_name,
    })

    return f"Task #{task_id} assigned to teammate '{teammate_name}'."


@register_tool(
    name="execute_parallel",
    description="Execute multiple tasks in parallel by spawning teammates. "
                "This is a high-level wrapper: for each task_id, spawns a teammate, "
                "assigns the task, and returns immediately. Results arrive asynchronously "
                "in your inbox. Use regulate_teammates() to monitor progress.",
    input_schema={
        "type": "object",
        "properties": {
            "task_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of task IDs to execute in parallel",
            },
            "role": {
                "type": "string",
                "description": "Role description for spawned teammates (e.g. 'paper-searcher')",
            },
        },
        "required": ["task_ids"],
    },
)
def execute_parallel(task_ids: list[str], role: str = "worker") -> str:
    """One-click parallel execution of multiple tasks.

    Claims each task first (atomic), then spawns the teammate — eliminates
    TOCTOU window between validation and claim.  Spawns with an empty prompt
    so only one task message reaches the inbox (from assign_task_to_teammate).
    """
    from ..task_system.manager import _manager

    global _parallel_batch_counter
    with _counter_lock:
        _parallel_batch_counter += 1
        batch_id = _parallel_batch_counter

    results = []
    for i, task_id in enumerate(task_ids):
        name = f"{role}-b{batch_id}-{i+1}"

        # 1. Validate task exists
        task = _manager.list_tasks.get(task_id)
        if task is None:
            results.append(f"  ✗ #{task_id}: not found")
            continue

        # 2. Claim atomically (eliminates TOCTOU with can_start check)
        claim_result = _manager.claim_task(task_id, owner=name)
        if claim_result.startswith("Error:"):
            results.append(f"  ✗ #{task_id}: {claim_result}")
            continue

        # 3. Spawn teammate (empty prompt — assign_task_to_teammate writes the real task)
        spawn_result = spawn_teammate_thread(name=name, role=role, prompt="")
        if spawn_result.startswith("Error:"):
            # Rollback: reset the task since spawn failed
            _manager.reset_task(task_id)
            results.append(f"  ✗ #{task_id}: {spawn_result}")
            continue

        # 4. Write task to inbox
        assign_result = assign_task_to_teammate(name, task_id)
        results.append(f"  → {name}: {assign_result}")

    return (
        f"Parallel execution started for {len(task_ids)} tasks:\n"
        + "\n".join(results)
        + "\n\nUse regulate_teammates() to monitor progress. "
        + "Results will arrive in your inbox as each teammate completes."
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
    from .tracker import tracker
    tracker.record_removal(name)
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
