"""Regulation module — lead-side tools for supervising parallel teammate execution.

Tools (only available to lead, excluded from teammate toolset):
  - regulate_teammates()    — show all active teammates and their task status
  - inspect_teammate()      — read detailed output from a specific teammate
  - reject_and_reassign()   — reject result, reset task to pending, optionally stop teammate
  - audit_stranded_tasks()  — safety net: detect tasks that have fallen through the cracks
"""

from . import tools  # noqa: F401 — registers regulation tools
from ..team.tracker import tracker  # canonical location

__all__ = ["tracker"]
