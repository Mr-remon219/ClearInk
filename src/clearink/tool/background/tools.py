"""Registered tools for background task management."""

import time

from ..register import register_tool
from .core import background_tasks, background_results, background_lock


@register_tool(
    name="get_background_result",
    description="Get the result of a background task by ID. "
                "Returns the result if complete, or status if still running.",
    input_schema={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Background task ID (e.g. 'bg_1')",
            },
        },
        "required": ["task_id"],
    },
)
def get_background_result(task_id: str) -> str:
    with background_lock:
        if task_id in background_results:
            return background_results[task_id]
        task = background_tasks.get(task_id)
        if task is None:
            return f"No background task found with id: {task_id}"
        return (
            f"Task {task_id} ({task['tool_name']}) is still {task['status']}, "
            f"started {time.time() - task['started_at']:.0f}s ago"
        )


@register_tool(
    name="list_background_tasks",
    description="List all background tasks with their current status.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def list_background_tasks() -> str:
    with background_lock:
        if not background_tasks and not background_results:
            return "(no background tasks)"

        lines = []
        for task_id, task in background_tasks.items():
            elapsed = time.time() - task["started_at"]
            lines.append(
                f"[{task['status']}] {task_id}: {task['tool_name']} "
                f"({elapsed:.0f}s elapsed)"
            )
        for task_id in background_results:
            if task_id not in background_tasks:
                lines.append(f"[done] {task_id}: result available (not yet collected)")

        return "\n".join(lines) if lines else "(no background tasks)"
