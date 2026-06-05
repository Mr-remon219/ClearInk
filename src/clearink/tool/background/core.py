"""Background task execution — shared state, detection, and lifecycle.

Keeps an in-memory registry of running background tasks.  Slow
operations are detected heuristically (keyword match on command
strings, large read limits) and automatically dispatched to a
daemon thread.
"""

from __future__ import annotations

import threading
import time

# ── Shared state ──────────────────────────────────────────

background_tasks: dict[str, dict] = {}   # id → task info + status
background_results: dict[str, str] = {}  # id → result string
_bg_counter: int = 0
background_lock = threading.Lock()

_SLOW_KEYWORDS = {
    "pip install", "pip3 install", "uv install", "uv add",
    "git clone", "git fetch", "git pull",
    "npm install", "npm run", "npx",
    "cargo build", "cargo install",
    "docker build", "docker pull", "docker compose",
    "make", "cmake", "bazel",
    "wget", "curl",
    "apt-get", "apt install", "brew install", "choco install",
    "conda install", "mamba install",
    "python -m pip", "python3 -m pip",
}

_RUNTIME_CONTROL_KEYS = {"run_in_background"}


# ── Helpers ───────────────────────────────────────────────

def strip_runtime_control_args(tool_input: dict) -> dict:
    return {
        k: v for k, v in dict(tool_input).items()
        if k not in _RUNTIME_CONTROL_KEYS
    }


def is_slow_operation(tool_name: str, tool_input: dict) -> bool:
    if tool_name == "spawn_subagent":
        return True

    if tool_name == "run_bash":
        timeout = tool_input.get("timeout", 0)
        if isinstance(timeout, (int, float)) and timeout > 120:
            return True
        command = str(tool_input.get("command", "")).lower()
        for kw in _SLOW_KEYWORDS:
            if kw in command:
                return True

    if tool_name == "read_file":
        limit = tool_input.get("limit", -1)
        if isinstance(limit, int) and limit > 5000:
            return True

    return False


def should_run_background(tool_name: str, tool_input: dict) -> bool:
    if tool_input.get("run_in_background") is True:
        return True
    return is_slow_operation(tool_name, tool_input)


def start_background_task(
    tool_name: str,
    tool_input: dict,
    handler,
) -> str:
    global _bg_counter
    with background_lock:
        _bg_counter += 1
        task_id = f"bg_{_bg_counter}"
        background_tasks[task_id] = {
            "id": task_id,
            "tool_name": tool_name,
            "tool_input": strip_runtime_control_args(tool_input),
            "status": "running",
            "started_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_and_store,
        args=(task_id, tool_name, tool_input, handler),
        daemon=True,
    )
    thread.start()

    return f"[Background] Task {task_id} started: {tool_name} — running in background"


def _run_and_store(
    task_id: str,
    tool_name: str,
    tool_input: dict,
    handler,
) -> None:
    try:
        result = handler(**strip_runtime_control_args(tool_input))
    except Exception as e:
        result = f"Error: {e}"

    with background_lock:
        if task_id in background_tasks:
            background_tasks[task_id]["status"] = "error" if result and str(result).startswith("Error:") else "done"
        background_results[task_id] = str(result)


def collect_background_results() -> list[str]:
    collected: list[str] = []
    with background_lock:
        done_ids = list(background_results.keys())
        for task_id in done_ids:
            result = background_results.pop(task_id, "")
            task_info = background_tasks.pop(task_id, {})
            status = task_info.get("status", "done")
            tool_name = task_info.get("tool_name", "?")
            collected.append(
                f"[Background] Task {task_id} ({tool_name}) {status}:\n{result}"
            )
    return collected
