"""Git command wrapper and worktree-name validation.

Safe, auditable interface to ``git worktree`` operations.  Every
git command is run in the repository root and captured via
``subprocess.run`` — no shell injection, no interactive prompts.
"""

from __future__ import annotations

import re
import subprocess

from clearink.config import REPO_ROOT

# Repository whose git worktrees are managed by this module.
_REPO_ROOT = REPO_ROOT

# Characters / patterns rejected in worktree names
_ILLEGAL_RE = re.compile(r'[\x00-\x1f\x7f/:*?"<>|\\\\]')
_MAX_NAME_LEN = 64


# ── Git command ───────────────────────────────────────────────

def run_git(args: list[str]) -> tuple[bool, str]:
    """Execute a git command in the repository root.

    Args:
        args: Git arguments WITHOUT the ``git`` prefix.
              e.g. ``["worktree", "list"]``, ``["status", "--porcelain"]``

    Returns:
        ``(True, stdout)`` on success (exit code 0).
        ``(False, stderr)`` on failure.
        Both strings are stripped of trailing whitespace.
    """
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,  # generous; git worktree ops are near-instant
        )
    except FileNotFoundError:
        return (False, "git command not found — is git installed and on PATH?")
    except subprocess.TimeoutExpired:
        return (False, "git command timed out after 30 s")

    if result.returncode == 0:
        return (True, result.stdout.strip())
    return (False, (result.stderr or result.stdout).strip())


# ── Name validation ───────────────────────────────────────────

def validate_worktree_name(name: str) -> tuple[bool, str]:
    """Validate a worktree name for use in paths and branch names.

    Rejects names that could enable path traversal, command injection,
    or OS-level naming violations.

    Rules (failure → returns ``(False, reason)``):
    - Must not be empty.
    - Must not be ``.`` or ``..``.
    - Must not contain ``/``, ``\\``, or control characters.
    - Must not contain Windows-forbidden chars: ``: * ? \" < > |``
    - Must not contain spaces.
    - Length ≤ 64 characters.
    - Must match ``^[a-zA-Z0-9][-_.a-zA-Z0-9]*$`` (safe slug).

    Args:
        name: The proposed worktree / directory name.

    Returns:
        ``(True, "")`` if valid, ``(False, reason)`` otherwise.
    """
    if not name:
        return (False, "name must not be empty")
    if name in (".", ".."):
        return (False, f"name must not be '{name}'")
    if len(name) > _MAX_NAME_LEN:
        return (False, f"name too long ({len(name)} > {_MAX_NAME_LEN})")
    if " " in name:
        return (False, "name must not contain spaces")
    if _ILLEGAL_RE.search(name):
        return (False, f"name contains illegal characters: {name!r}")

    # Must start with alphanumeric, then alphanumeric / dash / dot / underscore
    if not re.match(r'^[a-zA-Z0-9][-_.a-zA-Z0-9]*$', name):
        return (False, f"name must start with alphanumeric and use only [-_.a-zA-Z0-9]: {name!r}")

    return (True, "")
