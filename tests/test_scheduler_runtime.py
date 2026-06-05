from __future__ import annotations

from datetime import datetime
from queue import Empty

import pytest


@pytest.fixture
def isolated_scheduler(monkeypatch):
    import clearink.tool.scheduler.core as core

    original_jobs = dict(core.scheduled_jobs)
    original_busy = core._agent_busy
    original_loop = core._agent_loop_fn

    def drain_queue() -> None:
        while True:
            try:
                core._fire_queue.get_nowait()
            except Empty:
                break

    drain_queue()
    monkeypatch.setattr(core, "_save_jobs", lambda: None)
    core.scheduled_jobs.clear()
    core._agent_busy = False
    core._agent_loop_fn = None

    yield core

    drain_queue()
    core.scheduled_jobs.clear()
    core.scheduled_jobs.update(original_jobs)
    core._agent_busy = original_busy
    core._agent_loop_fn = original_loop


def test_enqueue_due_jobs_disables_one_shot_and_deduplicates_minute(
    isolated_scheduler,
    monkeypatch,
) -> None:
    from clearink.tool.scheduler.model import CronJob

    save_calls: list[str] = []
    monkeypatch.setattr(isolated_scheduler, "_save_jobs", lambda: save_calls.append("save"))
    job = CronJob(
        id="job1",
        cron="5 10 * * *",
        prompt="Run scheduled prompt",
        recurring=False,
        durable=True,
    )
    isolated_scheduler.scheduled_jobs[job.id] = job
    now = datetime(2026, 6, 5, 10, 5)

    changed = isolated_scheduler._enqueue_due_jobs(now)
    changed_again = isolated_scheduler._enqueue_due_jobs(now)

    assert changed is True
    assert changed_again is False
    assert save_calls == ["save"]
    assert job.enabled is False
    assert job.last_fired is not None
    assert job.last_fired_minute == "2026-06-05 10:05"
    assert isolated_scheduler._fire_queue.qsize() == 1


def test_process_next_queued_job_defers_when_agent_busy(isolated_scheduler) -> None:
    from clearink.tool.scheduler.model import CronJob

    isolated_scheduler._fire_queue.put(CronJob(
        id="busy",
        cron="* * * * *",
        prompt="wait",
    ))
    isolated_scheduler._agent_busy = True
    isolated_scheduler._agent_loop_fn = lambda _messages: None

    assert isolated_scheduler._process_next_queued_job() is False
    assert isolated_scheduler._fire_queue.qsize() == 1


def test_process_next_queued_job_runs_and_resets_busy(isolated_scheduler) -> None:
    from clearink.tool.scheduler.model import CronJob

    seen_messages: list[list[dict]] = []
    isolated_scheduler._fire_queue.put(CronJob(
        id="ready",
        cron="* * * * *",
        prompt="hello",
    ))
    isolated_scheduler._agent_loop_fn = lambda messages: seen_messages.append(messages)

    assert isolated_scheduler._process_next_queued_job() is True
    assert seen_messages == [[{"role": "user", "content": "[Scheduled: ready] hello"}]]
    assert isolated_scheduler.is_busy() is False
    assert isolated_scheduler._fire_queue.qsize() == 0


def test_process_next_queued_job_resets_busy_after_agent_exception(
    isolated_scheduler,
) -> None:
    from clearink.tool.scheduler.model import CronJob

    isolated_scheduler._fire_queue.put(CronJob(
        id="boom",
        cron="* * * * *",
        prompt="explode",
    ))

    def failing_agent_loop(_messages: list[dict]) -> None:
        raise RuntimeError("boom")

    isolated_scheduler._agent_loop_fn = failing_agent_loop

    assert isolated_scheduler._process_next_queued_job() is True
    assert isolated_scheduler.is_busy() is False
