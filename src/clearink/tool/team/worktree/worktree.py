"""Git worktree lifecycle management for task-isolated workspaces.

Each task can be assigned an independent git worktree (a linked
working directory on its own branch).  This isolates file operations
so teammates working on different tasks do not collide.

Key design: ``log_event`` is only called AFTER the git command
succeeds, so the event log always reflects reality.

Directory layout::

    data/.tasks/.worktrees/
        .mailboxes/         ← main-branch worktree
        task_1_alice/        ← worktree for task #1
        .events.jsonl        ← lifecycle event log
        bindings.json        ← task_id → worktree_name
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from filelock import FileLock

from ....config import WORKTREES_DIR
from ...register import register_tool
from .git_ops import run_git, validate_worktree_name

# ── Path constants ────────────────────────────────────────────

MAILBOXES_DIR = WORKTREES_DIR / ".mailboxes"
BINDINGS_PATH = WORKTREES_DIR / "bindings.json"
EVENTS_LOG = WORKTREES_DIR / ".events.jsonl"

_BINDINGS_LOCK_PATH = WORKTREES_DIR / ".bindings.lock"


# ── Internal helpers ──────────────────────────────────────────

def _worktree_path(name: str) -> Path:
    """Resolve a worktree name to its absolute filesystem path."""
    if name == ".mailboxes":
        return MAILBOXES_DIR
    return WORKTREES_DIR / name


def _branch_name(name: str) -> str:
    """Generate a git branch name for a worktree."""
    return f"worktree/{name}"


def _load_bindings() -> dict[str, str]:
    """Load the task_id → worktree_name mapping from disk."""
    if not BINDINGS_PATH.exists():
        return {}
    try:
        data = json.loads(BINDINGS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_bindings(bindings: dict[str, str]) -> None:
    """Write the binding table to disk under a file lock."""
    WORKTREES_DIR.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(_BINDINGS_LOCK_PATH), timeout=5)
    with lock:
        BINDINGS_PATH.write_text(
            json.dumps(bindings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _get_worktree_for_task(task_id: str) -> str | None:
    """Return the worktree name bound to *task_id*, or None."""
    bindings = _load_bindings()
    return bindings.get(task_id)


# ── Event logging ─────────────────────────────────────────────

def log_event(
    event_type: str,
    worktree_name: str,
    task_id: str = "",
) -> None:
    """Append a JSONL event to the worktree lifecycle log.

    This is a low-level function.  In normal usage it is called
    automatically by ``create_worktree`` / ``remove_worktree`` /
    ``keep_worktree`` — you rarely need to call it directly.

    Args:
        event_type:     One of ``"create"``, ``"remove"``, ``"keep"``,
                        ``"bind"``, ``"unbind"``.
        worktree_name:  The worktree name involved.
        task_id:        Associated task ID (can be empty).
    """
    WORKTREES_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "event": event_type,
        "worktree": worktree_name,
        "task_id": task_id,
    }
    with open(EVENTS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Public API ────────────────────────────────────────────────

def create_worktree(name: str, task_id: str = "") -> str:
    """Create an isolated git worktree on a new branch.

    1. Validates *name* against path-traversal / injection rules.
    2. Creates the directory via ``git worktree add <path> -b <branch>``.
    3. On git success: logs a ``"create"`` event and (if *task_id*
       is non-empty) binds the task to the worktree.

    Branch naming:
        - With *task_id*:  ``task/{task_id}``
        - Without:         ``worktree/{name}``

    Args:
        name:     Safe slug for directory and branch (see
                  :func:`validate_worktree_name`).
        task_id:  Optional task ID to bind this worktree to.

    Returns:
        Success message with path and branch info, or ``"Error: ..."``.
    """
    # Validate
    valid, reason = validate_worktree_name(name)
    if not valid:
        return f"Error: invalid worktree name — {reason}"

    path = _worktree_path(name)
    if path.exists():
        return f"Error: path already exists: {path}"

    branch = f"task/{task_id}" if task_id else _branch_name(name)

    # Create the worktree
    ok, output = run_git([
        "worktree", "add", str(path), "-b", branch,
    ])
    if not ok:
        return f"Error: git worktree add failed — {output}"

    # Only log + bind after git succeeds
    log_event("create", name, task_id)

    if task_id:
        bind_task_to_worktree(task_id, name)

    return (
        f"Worktree '{name}' created.\n"
        f"  path:   {path}\n"
        f"  branch: {branch}\n"
        f"  task:   {task_id or '(none)'}"
    )


def bind_task_to_worktree(task_id: str, worktree_name: str) -> str:
    """Record a mapping from *task_id* to *worktree_name*.

    This does **not** modify the task file's status — it only
    writes to the worktree bindings table.  Use it so that
    teammates can look up which worktree directory to ``chdir``
    into when they claim a task.

    Args:
        task_id:        Task ID (e.g. ``"1"``).
        worktree_name:  Worktree name to bind.

    Returns:
        ``"bound: <task_id> → <worktree_name>"`` or error string.
    """
    valid, reason = validate_worktree_name(worktree_name)
    if not valid:
        return f"Error: invalid worktree name — {reason}"

    path = _worktree_path(worktree_name)
    if not path.exists():
        return f"Error: worktree path does not exist: {path}"

    bindings = _load_bindings()
    bindings[str(task_id)] = worktree_name
    _save_bindings(bindings)

    log_event("bind", worktree_name, task_id)
    return f"bound: task {task_id} → worktree '{worktree_name}'"


def remove_worktree(name: str, discard_changes: bool = False) -> str:
    """Remove a git worktree and its branch.

    Args:
        name:             Worktree name to remove.
        discard_changes:  If ``True``, use ``--force`` to discard
                          uncommitted changes.

    Returns:
        Success message or ``"Error: ..."``.
    """
    valid, reason = validate_worktree_name(name)
    if not valid:
        return f"Error: invalid worktree name — {reason}"

    path = _worktree_path(name)
    if not path.exists():
        return f"Error: worktree path does not exist: {path}"

    args = ["worktree", "remove", str(path)]
    if discard_changes:
        args.append("--force")

    ok, output = run_git(args)
    if not ok:
        return f"Error: git worktree remove failed — {output}"

    # Only log after git succeeds
    log_event("remove", name)

    # Clean up binding
    bindings = _load_bindings()
    to_remove = [tid for tid, wn in bindings.items() if wn == name]
    if to_remove:
        for tid in to_remove:
            del bindings[tid]
        _save_bindings(bindings)
        for tid in to_remove:
            log_event("unbind", name, tid)

    return f"Worktree '{name}' removed."


def keep_worktree(name: str) -> str:
    """Declare that a worktree should be kept (not cleaned up).

    This is a no-op on the filesystem — it only writes a ``"keep"``
    event to the log.  Useful for audit trails and for distinguishing
    intentional keeps from forgotten cleanups.

    Args:
        name: Worktree name.

    Returns:
        Confirmation string.
    """
    valid, reason = validate_worktree_name(name)
    if not valid:
        return f"Error: invalid worktree name — {reason}"

    log_event("keep", name)
    return f"Worktree '{name}' kept."


# ── Registered tools ──────────────────────────────────────────

@register_tool(
    name="create_worktree",
    description="Create an isolated git worktree for a task. "
                "Each worktree gets its own directory and git branch, "
                "so file operations for different tasks never collide.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Safe slug for the worktree (alphanumeric + dash/dot/underscore, max 64 chars). "
                               "Used as both the directory name and part of the branch name.",
            },
            "task_id": {
                "type": "string",
                "description": "Optional task ID to bind this worktree to. "
                               "When set, the branch is named task/{task_id}.",
            },
        },
        "required": ["name"],
    },
)
def _tool_create_worktree(name: str, task_id: str = "") -> str:
    return create_worktree(name, task_id)


@register_tool(
    name="remove_worktree",
    description="Remove a git worktree (and its branch). "
                "Use discard_changes=True to force-delete even with "
                "uncommitted changes.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Worktree name to remove.",
            },
            "discard_changes": {
                "type": "boolean",
                "description": "If true, force-remove even with uncommitted changes.",
            },
        },
        "required": ["name"],
    },
)
def _tool_remove_worktree(name: str, discard_changes: bool = False) -> str:
    return remove_worktree(name, discard_changes)


@register_tool(
    name="keep_worktree",
    description="Mark a worktree to be kept (not deleted) after the task "
                "is complete.  This is a log-only operation — no git "
                "action is taken.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Worktree name to keep.",
            },
        },
        "required": ["name"],
    },
)
def _tool_keep_worktree(name: str) -> str:
    return keep_worktree(name)


@register_tool(
    name="bind_task_worktree",
    description="Bind a task ID to a worktree name.  This does NOT "
                "change the task status — it only records the mapping "
                "so teammates know which directory to work in.",
    input_schema={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID to bind.",
            },
            "worktree_name": {
                "type": "string",
                "description": "Worktree name the task is bound to.",
            },
        },
        "required": ["task_id", "worktree_name"],
    },
)
def _tool_bind_task_worktree(task_id: str, worktree_name: str) -> str:
    return bind_task_to_worktree(task_id, worktree_name)
