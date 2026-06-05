"""Git worktree management for task-isolated workspaces.

Creates and manages independent git worktrees under
``data/.tasks/.worktrees/`` so teammates working on different
tasks have isolated file systems and branches.

Key exports:
  create_worktree()       — ``git worktree add`` + event log + bind
  remove_worktree()       — ``git worktree remove`` + cleanup
  keep_worktree()         — log-only keep marker
  bind_task_to_worktree() — record task ↔ worktree mapping
  log_event()             — append JSONL lifecycle event
  run_git()               — safe subprocess wrapper
  validate_worktree_name() — reject path traversal / illegal chars
"""

from .git_ops import run_git, validate_worktree_name
from .worktree import (
    create_worktree,
    remove_worktree,
    keep_worktree,
    bind_task_to_worktree,
    log_event,
    _get_worktree_for_task,
    _worktree_path,
    MAILBOXES_DIR,
)

# Tool registration happens on import (via @register_tool in worktree.py)
# Activated by team/__init__.py:  from .worktree import worktree

__all__ = [
    "create_worktree",
    "remove_worktree",
    "keep_worktree",
    "bind_task_to_worktree",
    "log_event",
    "run_git",
    "validate_worktree_name",
    "_get_worktree_for_task",
    "_worktree_path",
    "MAILBOXES_DIR",
]
