"""Cron scheduler — state, cron matching, persistence, daemon loops."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from queue import Empty, Queue
from typing import Callable

from clearink.config import SCHEDULED_TASKS_DIR
from .model import CronJob

# ── Paths ─────────────────────────────────────────────────

_SCHEDULED_DIR = SCHEDULED_TASKS_DIR
_SCHEDULED_FILE = _SCHEDULED_DIR / ".scheduled_tasks.json"

# ── Shared state ──────────────────────────────────────────

scheduled_jobs: dict[str, CronJob] = {}
_fire_queue: Queue = Queue()
_agent_busy: bool = False
_agent_loop_fn: Callable | None = None
_lock = threading.RLock()
_threads_lock = threading.Lock()
_threads_started = False


# ── Busy / agent-loop injection ───────────────────────────

def set_busy(busy: bool) -> None:
    global _agent_busy
    with _lock:
        _agent_busy = busy


def is_busy() -> bool:
    with _lock:
        return _agent_busy


def set_agent_loop(fn: Callable) -> None:
    global _agent_loop_fn
    with _lock:
        _agent_loop_fn = fn
    ensure_scheduler_started()


def ensure_scheduler_started() -> None:
    global _threads_started
    with _threads_lock:
        if _threads_started:
            return
        _load_jobs()
        threading.Thread(target=cron_scheduler_loop, daemon=True).start()
        threading.Thread(target=queue_processor_loop, daemon=True).start()
        _threads_started = True


# ── Cron matching ─────────────────────────────────────────

def cron_matches(cron_expr: str, dt: datetime) -> bool:
    try:
        fields = cron_expr.strip().split()
        if len(fields) != 5:
            return False
        values = [dt.minute, dt.hour, dt.day, dt.month, (dt.weekday() + 1) % 7]
        for field, val in zip(fields, values):
            if not _match_field(field, val):
                return False
        return True
    except Exception:
        return False


def _match_field(field: str, value: int) -> bool:
    if field == "*":
        return True
    if field.startswith("*/"):
        step = int(field[2:])
        return value % step == 0
    parts = field.split(",")
    if len(parts) > 1:
        return any(_match_field(p.strip(), value) for p in parts)
    if "-" in field:
        lo, hi = field.split("-", 1)
        return int(lo) <= value <= int(hi)
    return int(field) == value


# ── Persistence ───────────────────────────────────────────

def _save_jobs() -> None:
    _SCHEDULED_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        durable = [j.to_dict() for j in scheduled_jobs.values() if j.durable]
    _SCHEDULED_FILE.write_text(
        json.dumps(durable, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _load_jobs() -> None:
    if not _SCHEDULED_FILE.exists():
        return
    try:
        data = json.loads(_SCHEDULED_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    with _lock:
        for item in data:
            job = CronJob.from_dict(item)
            job.enabled = True
            scheduled_jobs[job.id] = job


# ── Daemon loops ──────────────────────────────────────────

def _enqueue_due_jobs(now: datetime | None = None) -> bool:
    """Enqueue jobs matching *now* and return whether durable state changed."""
    now = now or datetime.now()
    should_save = False
    with _lock:
        jobs = list(scheduled_jobs.values())
        for job in jobs:
            if not job.enabled:
                continue
            if not job.recurring and job.last_fired is not None:
                continue
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            if job.last_fired_minute == current_minute:
                continue
            if cron_matches(job.cron, now):
                _fire_queue.put(job)
                job.last_fired = time.time()
                job.last_fired_minute = current_minute
                if not job.recurring:
                    job.enabled = False
                    should_save = True
    if should_save:
        _save_jobs()
    return should_save


def _process_next_queued_job() -> bool:
    """Run one queued job if the agent is available."""
    with _lock:
        agent_loop_fn = _agent_loop_fn
        can_run = not _agent_busy and agent_loop_fn is not None
    if not can_run:
        return False

    try:
        job = _fire_queue.get_nowait()
    except Empty:
        return False

    set_busy(True)
    try:
        agent_loop_fn([
            {"role": "user", "content": f"[Scheduled: {job.id}] {job.prompt}"},
        ])
    except Exception:
        pass
    finally:
        set_busy(False)
    return True


def cron_scheduler_loop() -> None:
    while True:
        _enqueue_due_jobs(datetime.now())
        time.sleep(30)


def queue_processor_loop() -> None:
    while True:
        _process_next_queued_job()
        time.sleep(5)
