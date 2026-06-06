"""Regulation tools — lead-side supervision of parallel teammate execution.

All tools in this module are registered for the lead agent only.
They are excluded from the teammate toolset (_EXCLUDED_TOOLS in lifecycle.py).
"""

from __future__ import annotations

import time

from clearink.hook import run_hooks
from clearink.tool.register import register_tool
from ..team.tracker import tracker


@register_tool(
    name="regulate_teammates",
    description="Show the execution status of all active teammates: "
                "which teammate is working on which task, elapsed time, status. "
                "Use this to monitor parallel execution progress.",
    input_schema={"type": "object", "properties": {}, "required": []},
)
def regulate_teammates() -> str:
    """List all active teammates and their task status."""
    from ..team.lifecycle import _active_teammates, _active_lock
    from ..task_system.manager import _manager

    with _active_lock:
        active = list(_active_teammates.keys())

    if not active:
        return "(no active teammates)"

    lines = ["Active Teammates:"]
    for name in sorted(active):
        record = tracker.get_teammate_status(name)
        if record:
            elapsed = time.time() - record["start_time"]
            task = _manager.list_tasks.get(record["task_id"], {})
            subject = task.get("subject", record["task_id"])
            lines.append(
                f"  [{record['status']}] {name} — Task #{record['task_id']}: {subject} "
                f"({elapsed:.0f}s elapsed)"
            )
        else:
            lines.append(f"  [?] {name} — no task assignment recorded")

    return "\n".join(lines)


@register_tool(
    name="inspect_teammate",
    description="Inspect the detailed output from a specific teammate. "
                "Reads the lead inbox to find messages sent by this teammate. "
                "Use this to review a teammate's work before completing their task.",
    input_schema={
        "type": "object",
        "properties": {
            "teammate_name": {
                "type": "string",
                "description": "Name of the teammate to inspect",
            },
        },
        "required": ["teammate_name"],
    },
)
def inspect_teammate(teammate_name: str) -> str:
    """View detailed output from a specific teammate (from lead inbox)."""
    from ..team.lifecycle import _active_teammates, _active_lock
    from ..team.bus import _bus

    with _active_lock:
        if teammate_name not in _active_teammates:
            return f"Error: no active teammate named '{teammate_name}'."

    # Non-destructive peek of lead inbox via bus API (preview — messages remain
    # in inbox for collect_teammate_messages to consume on next end_turn)
    all_msgs = _bus.peek("lead")
    messages = [m for m in all_msgs if m.get("from") == teammate_name]

    if not messages:
        return f"Teammate '{teammate_name}' has not reported any results yet."

    # Format output
    record = tracker.get_teammate_status(teammate_name)
    header = f"Teammate: {teammate_name}"
    if record:
        elapsed = time.time() - record.get("start_time", time.time())
        header += (
            f" | Task #{record['task_id']} | Status: {record['status']} "
            f"| {elapsed:.0f}s elapsed"
        )

    # Show most recent 3 results
    content = "\n---\n".join(
        m.get("content", str(m)) for m in messages[-3:]
    )
    return f"{header}\n{'-' * 40}\n{content}"


@register_tool(
    name="reject_and_reassign",
    description="Reject a teammate's result and reset the task for reassignment. "
                "Resets task status to pending so it can be assigned to another teammate "
                "or executed by the lead. Optionally stops the underperforming teammate.",
    input_schema={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID to reassign",
            },
            "from_teammate": {
                "type": "string",
                "description": "Teammate whose result is being rejected",
            },
            "reason": {
                "type": "string",
                "description": "Reason for rejection (for audit trail)",
            },
            "stop_teammate": {
                "type": "boolean",
                "description": "Also stop this teammate (default: true)",
            },
        },
        "required": ["task_id", "from_teammate"],
    },
)
def reject_and_reassign(
    task_id: str,
    from_teammate: str,
    reason: str = "",
    stop_teammate: bool = True,
) -> str:
    """Reject a teammate's result and reset the task to pending."""
    from ..task_system.manager import _manager

    task = _manager.list_tasks.get(task_id)
    if task is None:
        return f"Error: task #{task_id} not found."

    # Reset task via public TaskManager method
    reset_result = _manager.reset_task(task_id)
    if reset_result.startswith("Error:"):
        return reset_result

    # Record rejection in tracker (preserved for audit_stranded_tasks)
    tracker.record_rejection(task_id, from_teammate, reason)
    run_hooks("task_lifecycle", {
        "event": "rejected", "task_id": task_id,
        "from_teammate": from_teammate, "reason": reason,
    })

    msg = f"Task #{task_id} rejected from '{from_teammate}' and reset to pending."
    if reason:
        msg += f" Reason: {reason}"

    if stop_teammate:
        from ..team.tools import stop_teammate as _stop
        stop_result = _stop(from_teammate)
        msg += f"\n{stop_result}"

    return msg


@register_tool(
    name="audit_stranded_tasks",
    description="Safety net: scan all tasks for any that may have fallen through the cracks. "
                "Detects three categories: "
                "(1) Orphaned: in_progress tasks whose owner teammate no longer exists, "
                "(2) Rejected & unclaimed: tasks that were rejected/reassigned but never picked up again, "
                "(3) Idle: unblocked pending tasks with no active teammates working. "
                "Use this periodically to ensure no task is left behind.",
    input_schema={"type": "object", "properties": {}, "required": []},
)
def audit_stranded_tasks() -> str:
    """Safety check: find tasks that have fallen through the cracks."""
    from ..task_system.manager import _manager
    from ..team.lifecycle import _active_teammates, _active_lock

    # Acquire locks in consistent order (_active_lock then _manager._lock)
    # to prevent AB-BA deadlock with assign_task_to_teammate.
    with _active_lock:
        active_names = set(_active_teammates.keys())
        _manager.refresh()
        # Snapshot tasks under both locks to prevent iteration races
        tasks_snapshot = dict(_manager.list_tasks)

    stranded: list[str] = []

    for tid, task in tasks_snapshot.items():
        owner = task.get("owner", "")
        status = task.get("status", "")
        subject = task.get("subject", tid)

        # Case 1: Orphaned — in_progress but owner teammate no longer active
        if status == "in_progress" and owner and owner not in active_names:
            stranded.append(
                f"  ⚠ Orphaned: Task #{tid} '{subject}' "
                f"— owner '{owner}' no longer active (teammate exited or was stopped)"
            )
            continue

        # Case 2: Rejected & unclaimed — pending, unblocked, has rejection record
        if status == "pending" and _manager.can_start(tid):
            tr = tracker.get_task_record(tid)
            if tr and tr.get("status") == "rejected":
                stranded.append(
                    f"  🔄 Rejected & unclaimed: Task #{tid} '{subject}' "
                    f"— was rejected from '{tr.get('from_teammate', '?')}' "
                    f"({tr.get('reason', 'no reason given')}) but never reassigned"
                )
                continue

        # Case 3: Idle — unblocked but no active teammates at all
        if status == "pending" and _manager.can_start(tid) and not owner:
            if not active_names:
                stranded.append(
                    f"  💤 Idle: Task #{tid} '{subject}' "
                    f"— ready to execute but no active teammates are working"
                )
                continue

    if not stranded:
        return "✅ All tasks accounted for. No stranded, orphaned, or idle tasks detected."

    return (
        f"⚠ Found {len(stranded)} potential issue(s):\n\n"
        + "\n".join(stranded)
        + "\n\n── Suggested actions ──"
        + "\n  Orphaned → reject_and_reassign(task_id, from_teammate) then reassign"
        + "\n  Rejected → assign_task_to_teammate() or execute_parallel()"
        + "\n  Idle     → claim_task() to execute directly, or execute_parallel() to dispatch"
    )
