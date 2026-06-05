"""File-locked task board access for teammate idle polling.

Provides direct filesystem-level task operations that bypass the
in-memory TaskManager cache.  Uses the ``filelock`` library to
guarantee atomic read-modify-write across concurrent teammate threads.

Race-condition example without file locking:
  Thread A reads task #1 (status: pending)
  Thread B reads task #1 (status: pending)   ← stale
  Thread A writes status=in_progress
  Thread B writes status=in_progress          ← overwrites A's claim
Both threads think they own task #1.  FileLock prevents this.
"""

from __future__ import annotations

import json

from filelock import FileLock

from ....config import TASKS_DIR

_TASKS_LOCK_PATH = TASKS_DIR / ".tasks.lock"
_LOCK_TIMEOUT = 10  # seconds — caller retries next poll cycle on timeout


# ── Internal helpers ──────────────────────────────────────────

def _load_all_tasks_direct() -> dict[str, dict]:
    """Read every task JSON file from disk into a fresh dict.

    Handles missing directory, unreadable files, and JSON decode
    errors gracefully — corrupted files are silently skipped.
    """
    tasks: dict[str, dict] = {}
    if not TASKS_DIR.exists():
        return tasks

    for f in sorted(TASKS_DIR.glob("*.json")):
        if f.name == ".tasks.lock":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        # Ensure id field exists (backfill from stem if missing)
        if "id" not in data:
            data["id"] = f.stem
        tasks[data["id"]] = data

    return tasks


def _write_task_direct(task: dict) -> None:
    """Write a single task dict to its JSON file on disk."""
    task_id = task.get("id", "")
    if not task_id:
        return
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    path = TASKS_DIR / f"{task_id}.json"
    path.write_text(
        json.dumps(task, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _can_start_task(task: dict, all_tasks: dict[str, dict]) -> bool:
    """Return True if *task* is claimable: status pending, no owner,
    and every blockedBy dependency is completed."""
    if task.get("status") != "pending":
        return False
    if task.get("owner", ""):
        return False
    for dep_id in task.get("blockedBy", []) or []:
        dep = all_tasks.get(dep_id)
        if dep is None:
            return False  # Dependency missing → can't start
        if dep.get("status") != "completed":
            return False
    return True


# ── Public API ────────────────────────────────────────────────

def scan_unclaimed_tasks() -> list[dict]:
    """Scan the on-disk task board for all tasks a teammate can claim.

    Filter criteria (all must be satisfied):
    - ``status == "pending"``
    - ``owner`` is empty string
    - Every ``blockedBy`` task ID has ``status == "completed"``

    Uses a ``FileLock`` on ``.tasks.lock`` to get a consistent
    filesystem snapshot.  Returns tasks sorted by numeric ID
    (lowest-first) for deterministic claiming order.

    Returns:
        List of claimable task dicts.  Empty list when nothing
        is available or the lock cannot be acquired.
    """
    try:
        lock = FileLock(str(_TASKS_LOCK_PATH), timeout=_LOCK_TIMEOUT)
        with lock:
            all_tasks = _load_all_tasks_direct()
            candidates = []
            for task in all_tasks.values():
                if _can_start_task(task, all_tasks):
                    candidates.append(task)

    except Exception:
        # Lock timeout or filesystem error — caller retries next cycle
        return []

    # Sort by numeric ID for determism (lowest ID picked first)
    def _sort_key(t: dict) -> tuple[int, str]:
        tid = str(t.get("id", ""))
        try:
            return (0, int(tid))
        except ValueError:
            return (1, tid.lower())

    candidates.sort(key=_sort_key)
    return candidates


def claim_task(task_id: str, owner: str = "agent") -> str:
    """Claim a task with proper file-level locking.

    Performs an atomic read-validate-write cycle inside a ``FileLock``
    context manager.  Validates:
    - The task file exists.
    - ``status == "pending"`` and ``owner`` is empty.
    - All ``blockedBy`` dependencies are ``"completed"``.

    Args:
        task_id: The numeric task ID to claim (e.g. ``"1"``).
        owner:   Name to record in the task's owner field.

    Returns:
        ``"claimed: <subject>"`` on success.
        ``"Error: <reason>"`` on failure (task missing, already
        claimed, deps not met, or lock timeout).
    """
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        lock = FileLock(str(_TASKS_LOCK_PATH), timeout=_LOCK_TIMEOUT)
        with lock:
            all_tasks = _load_all_tasks_direct()
            task = all_tasks.get(task_id)

            if task is None:
                return f"Error: task '{task_id}' not found"

            if task.get("status") != "pending":
                return (
                    f"Error: task '{task_id}' is already "
                    f"'{task.get('status')}' (owner: {task.get('owner', 'unknown')})"
                )

            if task.get("owner", ""):
                return (
                    f"Error: task '{task_id}' already claimed by "
                    f"'{task.get('owner')}'"
                )

            # Verify dependencies
            for dep_id in task.get("blockedBy", []) or []:
                dep = all_tasks.get(dep_id)
                if dep is None:
                    return f"Error: dependency task '{dep_id}' not found"
                if dep.get("status") != "completed":
                    return (
                        f"Error: dependency '{dep_id}' ({dep.get('subject')}) "
                        f"is not completed (status: {dep.get('status')})"
                    )

            # All checks passed — claim the task
            task["status"] = "in_progress"
            task["owner"] = owner
            _write_task_direct(task)

    except Exception as e:
        return f"Error: could not acquire task lock ({e})"

    subject = task.get("subject", task_id)
    return f"claimed: {subject}"
