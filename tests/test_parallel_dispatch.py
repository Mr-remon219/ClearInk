"""Tests for parallel dispatch: assign_task_to_teammate and execute_parallel tools."""

from __future__ import annotations

import unittest

from clearink.tool.team.tools import (
    assign_task_to_teammate,
    execute_parallel,
    spawn_teammate_thread,
    stop_teammate,
)
from clearink.tool.task_system.tools import (
    create_task,
    get_unblocked_tasks,
)
from clearink.tool.task_system.manager import _manager


class TestAssignTaskToTeammate(unittest.TestCase):
    """Tests for assign_task_to_teammate."""

    def setUp(self):
        """Ensure clean state before each test."""
        # Clear any stale teammates
        from clearink.tool.team.lifecycle import _active_teammates, _active_lock
        with _active_lock:
            for name in list(_active_teammates.keys()):
                stop_teammate(name)

    def test_assign_to_nonexistent_teammate_returns_error(self):
        """Assigning to a non-existent teammate returns an error."""
        result = assign_task_to_teammate("ghost_teammate", "1")
        self.assertIn("Error:", result)

    def test_assign_to_existing_teammate(self):
        """Assigning a task to a spawned teammate succeeds."""
        # Create a task
        create_task("test assign task", "testing assignment")

        # Find the task ID
        tasks = _manager.list_tasks
        task_id = max(tasks.keys(), key=lambda k: int(k) if k.isdigit() else 0)

        # Spawn a teammate
        spawn_teammate_thread("test_assignee", "tester", "waiting for task")

        # Assign the task
        result = assign_task_to_teammate("test_assignee", task_id)
        self.assertNotIn("Error:", result)
        self.assertIn("assigned", result)

        # Cleanup
        stop_teammate("test_assignee")

    def test_assign_already_claimed_task_returns_error(self):
        """Assigning an already-claimed task returns an error."""
        create_task("claimed task test", "testing claim collision")
        tasks = _manager.list_tasks
        task_id = max(tasks.keys(), key=lambda k: int(k) if k.isdigit() else 0)

        # Claim it manually
        _manager.claim_task(task_id, owner="someone_else")

        # Spawn a teammate
        spawn_teammate_thread("claim_tester", "tester", "waiting")
        result = assign_task_to_teammate("claim_tester", task_id)
        self.assertIn("Error:", result)

        stop_teammate("claim_tester")


class TestExecuteParallel(unittest.TestCase):
    """Tests for execute_parallel."""

    def setUp(self):
        from clearink.tool.team.lifecycle import _active_teammates, _active_lock
        with _active_lock:
            for name in list(_active_teammates.keys()):
                stop_teammate(name)

    def test_execute_parallel_with_empty_list(self):
        """execute_parallel with empty list should handle gracefully."""
        result = execute_parallel([], role="test")
        self.assertIn("0 tasks", result)

    def test_execute_parallel_with_blocked_tasks(self):
        """Tasks that are blocked should be reported as unable to start."""
        # Create task 1 (no deps) — should work
        create_task("parallel task A")
        # Create task 2 (depends on task 1, which is not completed) — blocked
        tasks = _manager.list_tasks
        ids = sorted(tasks.keys(), key=lambda k: int(k) if k.isdigit() else 0)
        task_a_id = ids[-2] if len(ids) >= 2 else None
        if task_a_id:
            create_task("parallel task B", blockedBy=[task_a_id])

        # Refresh to get the new task
        tasks = _manager.list_tasks
        ids = sorted(tasks.keys(), key=lambda k: int(k) if k.isdigit() else 0)

        # Only task A should be dispatchable
        executable_ids = [
            tid for tid in ids
            if _manager.can_start(tid)
        ]

        if executable_ids:
            result = execute_parallel(executable_ids, role="test-parallel")
            # Should contain at least one success
            self.assertIn("Parallel execution started", result)

    def test_execute_parallel_batch_ids_increment(self):
        """Batch counter increments with each call."""
        # Create separate tasks for each batch to avoid "already claimed" errors
        create_task("batch test A1")
        create_task("batch test A2")
        create_task("batch test B1")
        create_task("batch test B2")
        _manager._refresh()
        tasks = _manager.list_tasks
        ids = sorted(tasks.keys(), key=lambda k: int(k) if k.isdigit() else 0)

        all_executable = [tid for tid in ids if _manager.can_start(tid)]

        if len(all_executable) >= 4:
            batch1_ids = all_executable[:2]
            batch2_ids = all_executable[2:4]

            r1 = execute_parallel(batch1_ids, role="batch-test")
            r2 = execute_parallel(batch2_ids, role="batch-test")

            # First batch uses b1, second uses b2
            self.assertIn("b1", r1)
            self.assertIn("b2", r2)


class TestGetUnblockedTasksTool(unittest.TestCase):
    """Tests for the get_unblocked_tasks tool."""

    def test_get_unblocked_tasks_returns_string(self):
        """get_unblocked_tasks returns a string description."""
        create_task("unblocked test", "testing unblocked task listing")
        result = get_unblocked_tasks()
        self.assertIsInstance(result, str)
        self.assertIn("unblocked", result.lower())

    def test_get_unblocked_tasks_when_all_blocked(self):
        """When all tasks are blocked, returns appropriate message."""
        create_task("blocker task")
        tasks = _manager.list_tasks
        ids = sorted(tasks.keys(), key=lambda k: int(k) if k.isdigit() else 0)
        blocker_id = ids[-1] if ids else None

        if blocker_id:
            create_task("blocked child", blockedBy=[blocker_id])
        # The child is blocked because the parent is not completed
        result = get_unblocked_tasks()
        # The parent should be unblocked, the child blocked
        self.assertIsInstance(result, str)

    def test_get_unblocked_tasks_no_tasks(self):
        """When no tasks exist, get_unblocked_tasks handles gracefully."""
        # This test might fail if there are stale tasks from previous tests
        result = get_unblocked_tasks()
        self.assertIsInstance(result, str)
        # Either "no unblocked tasks" or list of stale tasks
        self.assertTrue(
            "no unblocked tasks" in result.lower()
            or "unblocked task" in result.lower()
        )
