"""Teammate idle-polling and autonomous task claiming.

Provides the IDLE-phase polling loop that lets teammates discover
and claim work from the shared task board when their inbox is empty.

Key exports:
  PollResult              — Enum: SHUTDOWN | WORK
  idle_poll()             — IDLE-phase polling loop
  inject_identity_message() — Prepend identity after compaction
  scan_unclaimed_tasks()  — File-locked scan of the task board
  claim_task()            — File-locked claim (read-modify-write)
"""

from .poller import PollResult, idle_poll, inject_identity_message
from .task_scanner import scan_unclaimed_tasks, claim_task

__all__ = [
    "PollResult",
    "idle_poll",
    "inject_identity_message",
    "scan_unclaimed_tasks",
    "claim_task",
]
