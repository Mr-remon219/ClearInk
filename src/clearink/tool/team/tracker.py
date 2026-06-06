"""ExecutionTracker — in-memory tracking of teammate assignments.

Uses a dual-index design to prevent history loss:
  - _executions: teammate_name → current status (overwritten on reassignment)
  - _rejections: task_id → rejection record (append-only, never overwritten)
This ensures audit_stranded_tasks can always find rejected tasks even after
the teammate who owned them gets a new assignment.
"""

from __future__ import annotations

import threading
import time


class ExecutionTracker:
    """Tracks which teammate is working on which task."""

    def __init__(self):
        self._executions: dict[str, dict] = {}  # teammate_name → current record
        self._rejections: dict[str, dict] = {}  # task_id → rejection record (append-only)
        self._lock = threading.RLock()

    def record_assignment(self, teammate: str, task_id: str):
        """Record a new task assignment (may overwrite previous status for this teammate)."""
        with self._lock:
            self._executions[teammate] = {
                "task_id": task_id,
                "start_time": time.time(),
                "status": "working",
            }

    def record_completion(self, teammate: str):
        """Mark teammate's current task as completed."""
        with self._lock:
            if teammate in self._executions:
                self._executions[teammate]["status"] = "completed"

    def record_rejection(self, task_id: str, from_teammate: str, reason: str = ""):
        """Record a task rejection. Stored in _rejections (append-only by task_id)
        so it survives teammate reassignment or removal."""
        with self._lock:
            self._rejections[task_id] = {
                "task_id": task_id,
                "from_teammate": from_teammate,
                "reason": reason,
                "status": "rejected",
                "time": time.time(),
            }
            # Also update teammate's current status if still tracked
            if from_teammate in self._executions:
                self._executions[from_teammate]["status"] = "rejected"

    def record_removal(self, teammate: str):
        """Remove a teammate from active tracking."""
        with self._lock:
            self._executions.pop(teammate, None)

    def get_all_active(self) -> dict[str, dict]:
        """Get all currently active teammate records."""
        with self._lock:
            return dict(self._executions)

    def get_teammate_status(self, teammate: str) -> dict | None:
        """Get current status for a specific teammate."""
        with self._lock:
            return self._executions.get(teammate)

    def get_task_record(self, task_id: str) -> dict | None:
        """Check if a task has a rejection record (from _rejections)."""
        with self._lock:
            return self._rejections.get(task_id)

    def get_teammate_by_task(self, task_id: str) -> str | None:
        """Reverse lookup: find which teammate is assigned to a task."""
        with self._lock:
            for name, record in self._executions.items():
                if record.get("task_id") == task_id:
                    return name
        return None


# Module-level singleton
tracker = ExecutionTracker()
