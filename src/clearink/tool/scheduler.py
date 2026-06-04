from __future__ import annotations
import json
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Callable

from .register import register_tool

# ── Paths ─────────────────────────────────────────────────
_SCHEDULED_DIR = Path(__file__).resolve().parents[3] / "data" / ".scheduled_tasks"
_SCHEDULED_FILE = _SCHEDULED_DIR / ".scheduled_tasks.json"

# ── CronJob ───────────────────────────────────────────────

@dataclass
class CronJob:
    id: str
    cron: str
    prompt: str
    recurring: bool = True
    durable: bool = True
    enabled: bool = True
    last_fired: float | None = None
    last_fired_minute: str | None = None  # "YYYY-MM-DD HH:MM" — prevents double-fire
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> CronJob:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Shared state ──────────────────────────────────────────
scheduled_jobs: dict[str, CronJob] = {}
_fire_queue: Queue = Queue()
_agent_busy: bool = False
_agent_loop_fn: Callable | None = None
_lock = threading.RLock()
_threads_lock = threading.Lock()
_threads_started = False


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

def cron_scheduler_loop() -> None:
    while True:
        now = datetime.now()
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
        time.sleep(30)


def queue_processor_loop() -> None:
    while True:
        with _lock:
            agent_loop_fn = _agent_loop_fn
            can_run = not _agent_busy and agent_loop_fn is not None
        if not _fire_queue.empty() and can_run:
            job = _fire_queue.get()
            set_busy(True)
            try:
                agent_loop_fn([
                    {"role": "user", "content": f"[Scheduled: {job.id}] {job.prompt}"},
                ])
            except Exception:
                pass
            finally:
                set_busy(False)
        time.sleep(5)


# ── Tools ─────────────────────────────────────────────────

@register_tool(
    name="schedule_cron",
    description="Schedule a recurring or one-shot cron job. The prompt will be "
                "injected as a user message when the cron fires. Standard 5-field "
                "cron: minute hour dom month dow (dow: 0=Sun). "
                "Recurring jobs auto-expire after 7 days.",
    input_schema={
        "type": "object",
        "properties": {
            "cron": {
                "type": "string",
                "description": "5-field cron expression, e.g. '*/5 * * * *' (every 5 min), '0 9 * * 1-5' (weekdays 9am)",
            },
            "prompt": {
                "type": "string",
                "description": "The prompt to enqueue when the cron fires",
            },
            "recurring": {
                "type": "boolean",
                "description": "Repeat on every cron match (true) or fire once (false). Default true.",
            },
            "durable": {
                "type": "boolean",
                "description": "Persist to JSON so the job survives restarts. Default true.",
            },
        },
        "required": ["cron", "prompt"],
    },
)
def schedule_cron(
    cron: str,
    prompt: str,
    recurring: bool = True,
    durable: bool = True,
) -> str:
    ensure_scheduler_started()
    fields = cron.strip().split()
    if len(fields) != 5:
        return f"Error: cron expression must have 5 fields, got {len(fields)}: {cron!r}"

    bounds = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    for i, cron_field in enumerate(fields):
        try:
            _validate_cron_field(cron_field, *bounds[i])
        except ValueError as e:
            field_names = ["minute", "hour", "dom", "month", "dow"]
            return f"Error: invalid cron field '{field_names[i]}' ({cron_field}): {e}"

    job_id = uuid.uuid4().hex[:12]
    job = CronJob(
        id=job_id,
        cron=cron,
        prompt=prompt,
        recurring=recurring,
        durable=durable,
    )

    with _lock:
        scheduled_jobs[job_id] = job

    if durable:
        _save_jobs()

    return (
        f"Job scheduled: {job_id}\n"
        f"  cron: {cron}\n"
        f"  recurring: {recurring}\n"
        f"  durable: {durable}\n"
        f"  prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}"
    )


def _validate_cron_field(field: str, min_value: int, max_value: int) -> None:
    if field == "*":
        return
    if field.startswith("*/"):
        step = int(field[2:])
        if step <= 0:
            raise ValueError("step must be greater than zero")
        return
    for part in field.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            lo_i = int(lo)
            hi_i = int(hi)
            if lo_i > hi_i:
                raise ValueError("range start must be <= range end")
            _validate_value(lo_i, min_value, max_value)
            _validate_value(hi_i, min_value, max_value)
        else:
            _validate_value(int(part), min_value, max_value)


def _validate_value(value: int, min_value: int, max_value: int) -> None:
    if value < min_value or value > max_value:
        raise ValueError(f"value must be between {min_value} and {max_value}")


@register_tool(
    name="list_scheduled_jobs",
    description="List all scheduled cron jobs with their status and next trigger.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def list_scheduled_jobs() -> str:
    ensure_scheduler_started()
    with _lock:
        if not scheduled_jobs:
            return "(no scheduled jobs)"
        lines = []
        for job in scheduled_jobs.values():
            status = "enabled" if job.enabled else "disabled"
            rec = "recurring" if job.recurring else "one-shot"
            dur = "durable" if job.durable else "memory"
            last = (
                datetime.fromtimestamp(job.last_fired).strftime("%Y-%m-%d %H:%M:%S")
                if job.last_fired
                else "never"
            )
            lines.append(
                f"[{status}] {job.id}: {job.cron} ({rec}, {dur})\n"
                f"  last: {last}\n"
                f"  prompt: {job.prompt[:80]}{'...' if len(job.prompt) > 80 else ''}"
            )
        return "\n".join(lines)


@register_tool(
    name="cancel_scheduled_job",
    description="Cancel and remove a scheduled cron job by ID.",
    input_schema={
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The job ID to cancel (from list_scheduled_jobs)",
            },
        },
        "required": ["job_id"],
    },
)
def cancel_scheduled_job(job_id: str) -> str:
    ensure_scheduler_started()
    with _lock:
        job = scheduled_jobs.pop(job_id, None)
    if job is None:
        return f"Error: no scheduled job found with id: {job_id}"
    if job.durable:
        _save_jobs()
    return f"Job {job_id} cancelled: {job.cron} — {job.prompt[:80]}"

