"""TaskManager — DAG task management with persistence to JSON files."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ...config import TASKS_DIR

_STATUS_ICONS = {
    "pending": " ",
    "in_progress": "→",
    "completed": "✓",
}


def _task_file(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def _write_task(task: dict) -> None:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    _task_file(task["id"]).write_text(
        json.dumps(task, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_all_tasks() -> dict[str, dict]:
    tasks: dict[str, dict] = {}
    if not TASKS_DIR.exists():
        return tasks
    for f in sorted(TASKS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if "id" not in data:
                data["id"] = f.stem
            tasks[data["id"]] = data
        except (json.JSONDecodeError, OSError):
            continue
    return tasks


def _max_id(tasks: dict[str, dict]) -> int:
    n = 0
    for tid in tasks:
        try:
            n = max(n, int(tid))
        except ValueError:
            pass
    return n


def _task_sort_key(task_id: str) -> tuple[int, int | str]:
    try:
        return (0, int(task_id))
    except ValueError:
        return (1, task_id)


class TaskManager:
    def __init__(self):
        self.list_tasks: dict[str, dict] = _load_all_tasks()
        self._counter: int = _max_id(self.list_tasks)
        self._lock = threading.RLock()

    # ── public API ──────────────────────────────────────

    def create_task(
        self,
        subject: str,
        description: str = "",
        blockedBy: list[str] | None = None,
    ) -> str:
        with self._lock:
            blocked = list(dict.fromkeys(blockedBy or []))

            for bid in blocked:
                if bid not in self.list_tasks:
                    return f"Error: blockedBy task '{bid}' does not exist. Create it first."

            self._counter += 1
            task_id = str(self._counter)

            task = {
                "id": task_id,
                "subject": subject,
                "description": description,
                "status": "pending",
                "owner": "",
                "blockedBy": blocked,
                "blocks": [],
            }
            self.list_tasks[task_id] = task

            for bid in blocked:
                blocks = self.list_tasks[bid].setdefault("blocks", [])
                if task_id not in blocks:
                    blocks.append(task_id)
                _write_task(self.list_tasks[bid])

            _write_task(task)
            return self._format_task(task_id)

    def can_start(self, task_id: str) -> bool:
        with self._lock:
            task = self.list_tasks.get(task_id)
            if task is None:
                return False
            if task["status"] != "pending":
                return False
            for bid in task["blockedBy"]:
                dep = self.list_tasks.get(bid)
                if dep is None or dep["status"] != "completed":
                    return False
            return True

    def claim_task(self, task_id: str, owner: str = "agent") -> str:
        with self._lock:
            task = self.list_tasks.get(task_id)
            if task is None:
                return f"Error: task '{task_id}' not found."

            if task["status"] != "pending":
                return f"Error: task '{task_id}' is already {task['status']} (owner: {task.get('owner', 'none')})."

            blocked = [bid for bid in task["blockedBy"]
                       if self.list_tasks.get(bid, {}).get("status") != "completed"]
            if blocked:
                return f"Error: task '{task_id}' is blocked by: {blocked}"

            task["status"] = "in_progress"
            task["owner"] = owner
            _write_task(task)
            return f"Task '{task_id}' claimed by {owner}."

    def complete_task(self, task_id: str) -> str:
        with self._lock:
            task = self.list_tasks.get(task_id)
            if task is None:
                return f"Error: task '{task_id}' not found."

            if task["status"] != "in_progress":
                return f"Error: task '{task_id}' is {task['status']}, not in_progress."

            task["status"] = "completed"
            task["owner"] = ""
            _write_task(task)

            unblocked = []
            for child_id in task["blocks"]:
                child = self.list_tasks.get(child_id)
                if child and child["status"] == "pending" and self.can_start(child_id):
                    unblocked.append(child_id)

            msg = f"Task '{task_id}' completed."
            if unblocked:
                msg += f" Unblocked: {unblocked}"
            return msg

    def get_task(self, task_id: str) -> str:
        with self._lock:
            self._refresh()
            task = self.list_tasks.get(task_id)
            if task is None:
                return f"Error: task '{task_id}' not found."
            return json.dumps(task, ensure_ascii=False, indent=2)

    def format_task_list(self) -> str:
        with self._lock:
            self._refresh()
            if not self.list_tasks:
                return "(no tasks)"

            lines = []
            for tid in sorted(self.list_tasks, key=_task_sort_key):
                t = self.list_tasks[tid]
                icon = _STATUS_ICONS.get(t["status"], "?")
                owner = f" — {t['owner']}" if t.get("owner") else ""
                blocked = f" (blockedBy: {t['blockedBy']})" if t.get("blockedBy") else ""
                lines.append(
                    f"[{icon}] #{tid}: {t['subject']}{owner}{blocked}"
                )
            return "\n".join(lines)

    # ── helpers ─────────────────────────────────────────

    def _refresh(self) -> None:
        """Reload all tasks from disk into the in-memory cache."""
        disk_tasks = _load_all_tasks()
        for tid, task in disk_tasks.items():
            self.list_tasks[tid] = task
        disk_ids = set(disk_tasks.keys())
        for tid in list(self.list_tasks.keys()):
            if tid not in disk_ids:
                del self.list_tasks[tid]

    def _format_task(self, task_id: str) -> str:
        with self._lock:
            t = self.list_tasks.get(task_id)
            if t is None:
                return f"Error: task '{task_id}' not found."
            icon = _STATUS_ICONS.get(t["status"], "?")
            return (
                f"[{icon}] #{task_id}: {t['subject']}\n"
                f"  status: {t['status']}\n"
                f"  blockedBy: {t.get('blockedBy', [])}\n"
                f"  blocks: {t.get('blocks', [])}"
            )


# ── singleton ───────────────────────────────────────────

_manager = TaskManager()
