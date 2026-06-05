"""Registered tools for DAG task management — all delegate to the TaskManager singleton."""

from clearink.hook import run_hooks
from ..register import register_tool
from .manager import _manager


@register_tool(
    name="create_task",
    description="Create a new task with optional dependencies (blockedBy). "
                "Tasks form a DAG: a task can only be claimed when all its blockedBy "
                "tasks are completed.",
    input_schema={
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Short task title (imperative form)"},
            "description": {"type": "string", "description": "What needs to be done"},
            "blockedBy": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Task IDs this task depends on",
            },
        },
        "required": ["subject"],
    },
)
def create_task(subject: str, description: str = "", blockedBy: list[str] | None = None) -> str:
    result = _manager.create_task(subject, description, blockedBy)
    if not result.startswith("Error:"):
        run_hooks("task_lifecycle", {"event": "created", "subject": subject})
    return result


@register_tool(
    name="claim_task",
    description="Claim a task to start working on it. "
                "Only succeeds when all dependencies (blockedBy) are completed "
                "and the task is still pending (prevents double-claiming).",
    input_schema={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID to claim"},
            "owner": {"type": "string", "description": "Who is claiming (default: agent)"},
        },
        "required": ["task_id"],
    },
)
def claim_task(task_id: str, owner: str = "agent") -> str:
    result = _manager.claim_task(task_id, owner)
    if not result.startswith("Error:"):
        run_hooks("task_lifecycle", {"event": "claimed", "task_id": task_id, "owner": owner})
    return result


@register_tool(
    name="complete_task",
    description="Mark a task as completed. "
                "Automatically unlocks any dependent tasks that now have all "
                "prerequisites satisfied.",
    input_schema={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID to complete"},
        },
        "required": ["task_id"],
    },
)
def complete_task(task_id: str) -> str:
    result = _manager.complete_task(task_id)
    if not result.startswith("Error:"):
        run_hooks("task_lifecycle", {"event": "completed", "task_id": task_id})
    return result


@register_tool(
    name="get_task",
    description="Get full details of a specific task by ID.",
    input_schema={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID to look up"},
        },
        "required": ["task_id"],
    },
)
def get_task(task_id: str) -> str:
    return _manager.get_task(task_id)


@register_tool(
    name="list_tasks",
    description="List all tasks with status, owner, and dependency summaries.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def list_tasks() -> str:
    return _manager.format_task_list()


@register_tool(
    name="check_task",
    description="Check whether a task can be started (all dependencies completed).",
    input_schema={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID to check"},
        },
        "required": ["task_id"],
    },
)
def check_task(task_id: str) -> str:
    with _manager._lock:
        task = _manager.list_tasks.get(task_id)
        if task is None:
            return f"Error: task '{task_id}' not found."
        if _manager.can_start(task_id):
            return f"Task '{task_id}' ({task['subject']}) is ready to start."
        blocked = [bid for bid in task.get("blockedBy", [])
                   if _manager.list_tasks.get(bid, {}).get("status") != "completed"]
        if task["status"] != "pending":
            return f"Task '{task_id}' is {task['status']}."
        return f"Task '{task_id}' is blocked by: {blocked}"
