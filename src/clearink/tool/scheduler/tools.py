"""Registered tools for cron job scheduling."""

from __future__ import annotations

import uuid
from datetime import datetime

from ..register import register_tool
from .core import ensure_scheduler_started, scheduled_jobs, _lock, _save_jobs
from .model import CronJob


# ── Validation helpers ────────────────────────────────────

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
