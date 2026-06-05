"""Tests for clearink.tool.team.idle.task_scanner."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from clearink.tool.team.idle.task_scanner import (
    _can_start_task,
    scan_unclaimed_tasks,
    claim_task,
)


class TestCanStartTask(unittest.TestCase):
    """_can_start_task determines whether a task is claimable."""

    def test_pending_no_owner_no_deps(self):
        task = {"id": "1", "status": "pending", "owner": "", "blockedBy": []}
        self.assertTrue(_can_start_task(task, {}))

    def test_pending_no_blockedby_key(self):
        task = {"id": "1", "status": "pending", "owner": ""}
        self.assertTrue(_can_start_task(task, {}))

    def test_pending_has_owner(self):
        task = {"id": "1", "status": "pending", "owner": "alice", "blockedBy": []}
        self.assertFalse(_can_start_task(task, {}))

    def test_pending_blocked_by_incomplete_dep(self):
        dep = {"id": "2", "status": "in_progress"}
        task = {"id": "1", "status": "pending", "owner": "", "blockedBy": ["2"]}
        all_tasks = {"2": dep}
        self.assertFalse(_can_start_task(task, all_tasks))

    def test_pending_blocked_by_pending_dep(self):
        dep = {"id": "2", "status": "pending"}
        task = {"id": "1", "status": "pending", "owner": "", "blockedBy": ["2"]}
        all_tasks = {"2": dep}
        self.assertFalse(_can_start_task(task, all_tasks))

    def test_pending_blocked_by_completed_dep(self):
        dep = {"id": "2", "status": "completed"}
        task = {"id": "1", "status": "pending", "owner": "", "blockedBy": ["2"]}
        all_tasks = {"2": dep}
        self.assertTrue(_can_start_task(task, all_tasks))

    def test_in_progress(self):
        task = {"id": "1", "status": "in_progress", "owner": "alice", "blockedBy": []}
        self.assertFalse(_can_start_task(task, {}))

    def test_completed(self):
        task = {"id": "1", "status": "completed", "owner": "", "blockedBy": []}
        self.assertFalse(_can_start_task(task, {}))

    def test_blocked_by_missing_dep(self):
        task = {"id": "1", "status": "pending", "owner": "", "blockedBy": ["999"]}
        all_tasks = {}
        self.assertFalse(_can_start_task(task, all_tasks))

    def test_blocked_by_none(self):
        task = {"id": "1", "status": "pending", "owner": "", "blockedBy": None}
        self.assertTrue(_can_start_task(task, {}))


class TestScanUnclaimedTasks(unittest.TestCase):
    """scan_unclaimed_tasks finds only claimable tasks from disk."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.tasks_dir = self.temp_dir / ".tasks"
        self.tasks_dir.mkdir()
        self.mock_lock = MagicMock()
        self.mock_lock.__enter__.return_value = None
        self.mock_lock.__exit__.return_value = None

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_task(self, task_id: str, data: dict):
        path = self.tasks_dir / f"{task_id}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @patch("filelock.FileLock")
    def test_finds_only_claimable(self, mock_filelock):
        mock_filelock.return_value = self.mock_lock

        self._write_task("1", {"id": "1", "subject": "claimable", "status": "pending", "owner": "", "blockedBy": []})
        self._write_task("2", {"id": "2", "subject": "has-owner", "status": "pending", "owner": "bob", "blockedBy": []})
        self._write_task("3", {"id": "3", "subject": "in-progress", "status": "in_progress", "owner": "carol", "blockedBy": []})
        self._write_task("4", {"id": "4", "subject": "completed", "status": "completed", "owner": "", "blockedBy": []})

        with patch("clearink.tool.team.idle.task_scanner.TASKS_DIR", self.tasks_dir):
            results = scan_unclaimed_tasks()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "1")

    @patch("filelock.FileLock")
    def test_blocked_dep_not_ready(self, mock_filelock):
        mock_filelock.return_value = self.mock_lock

        self._write_task("5", {"id": "5", "subject": "dep-not-done", "status": "pending", "owner": "", "blockedBy": ["6"]})
        self._write_task("6", {"id": "6", "subject": "dep", "status": "in_progress", "owner": "", "blockedBy": []})

        with patch("clearink.tool.team.idle.task_scanner.TASKS_DIR", self.tasks_dir):
            results = scan_unclaimed_tasks()

        self.assertEqual(len(results), 0)

    @patch("filelock.FileLock")
    def test_blocked_dep_completed(self, mock_filelock):
        mock_filelock.return_value = self.mock_lock

        self._write_task("7", {"id": "7", "subject": "ready-now", "status": "pending", "owner": "", "blockedBy": ["8"]})
        self._write_task("8", {"id": "8", "subject": "done-dep", "status": "completed", "owner": "", "blockedBy": []})

        with patch("clearink.tool.team.idle.task_scanner.TASKS_DIR", self.tasks_dir):
            results = scan_unclaimed_tasks()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "7")

    @patch("filelock.FileLock")
    def test_empty_tasks_dir(self, mock_filelock):
        mock_filelock.return_value = self.mock_lock
        empty_dir = self.temp_dir / "empty"
        empty_dir.mkdir()

        with patch("clearink.tool.team.idle.task_scanner.TASKS_DIR", empty_dir):
            results = scan_unclaimed_tasks()

        self.assertEqual(results, [])

    @patch("filelock.FileLock")
    def test_sorts_by_numeric_id(self, mock_filelock):
        mock_filelock.return_value = self.mock_lock

        self._write_task("3", {"id": "3", "subject": "c", "status": "pending", "owner": "", "blockedBy": []})
        self._write_task("1", {"id": "1", "subject": "a", "status": "pending", "owner": "", "blockedBy": []})
        self._write_task("2", {"id": "2", "subject": "b", "status": "pending", "owner": "", "blockedBy": []})

        with patch("clearink.tool.team.idle.task_scanner.TASKS_DIR", self.tasks_dir):
            results = scan_unclaimed_tasks()

        self.assertEqual([r["id"] for r in results], ["1", "2", "3"])


class TestClaimTask(unittest.TestCase):
    """claim_task claims a single task with file-level validation."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.tasks_dir = self.temp_dir / ".tasks"
        self.tasks_dir.mkdir()
        self.mock_lock = MagicMock()
        self.mock_lock.__enter__.return_value = None
        self.mock_lock.__exit__.return_value = None

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_task(self, task_id: str, data: dict):
        path = self.tasks_dir / f"{task_id}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _read_task(self, task_id: str) -> dict | None:
        path = self.tasks_dir / f"{task_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @patch("filelock.FileLock")
    def test_successful_claim(self, mock_filelock):
        mock_filelock.return_value = self.mock_lock
        self._write_task("1", {"id": "1", "subject": "my-task", "status": "pending", "owner": "", "blockedBy": []})

        with patch("clearink.tool.team.idle.task_scanner.TASKS_DIR", self.tasks_dir):
            result = claim_task("1", owner="test-agent")

        self.assertEqual(result, "claimed: my-task")
        task = self._read_task("1")
        self.assertEqual(task["status"], "in_progress")
        self.assertEqual(task["owner"], "test-agent")

    @patch("filelock.FileLock")
    def test_double_claim_fails(self, mock_filelock):
        mock_filelock.return_value = self.mock_lock
        self._write_task("1", {"id": "1", "subject": "my-task", "status": "pending", "owner": "", "blockedBy": []})

        with patch("clearink.tool.team.idle.task_scanner.TASKS_DIR", self.tasks_dir):
            result1 = claim_task("1", owner="Alice")
            result2 = claim_task("1", owner="Bob")

        self.assertEqual(result1, "claimed: my-task")
        self.assertIn("Error", result2)

    @patch("filelock.FileLock")
    def test_dependency_not_met_fails(self, mock_filelock):
        mock_filelock.return_value = self.mock_lock
        self._write_task("1", {"id": "1", "subject": "blocked", "status": "pending", "owner": "", "blockedBy": ["2"]})
        self._write_task("2", {"id": "2", "subject": "prereq", "status": "pending", "owner": "", "blockedBy": []})

        with patch("clearink.tool.team.idle.task_scanner.TASKS_DIR", self.tasks_dir):
            result = claim_task("1", owner="Alice")

        self.assertIn("Error", result)
        task = self._read_task("1")
        self.assertEqual(task["status"], "pending")

    @patch("filelock.FileLock")
    def test_claim_nonexistent_task(self, mock_filelock):
        mock_filelock.return_value = self.mock_lock

        with patch("clearink.tool.team.idle.task_scanner.TASKS_DIR", self.tasks_dir):
            result = claim_task("999", owner="Alice")

        self.assertIn("Error", result)
        self.assertIn("not found", result)

    @patch("filelock.FileLock")
    def test_dependency_not_found_fails(self, mock_filelock):
        mock_filelock.return_value = self.mock_lock
        self._write_task("1", {"id": "1", "subject": "blocked-by-missing", "status": "pending", "owner": "", "blockedBy": ["missing-dep"]})

        with patch("clearink.tool.team.idle.task_scanner.TASKS_DIR", self.tasks_dir):
            result = claim_task("1", owner="Alice")

        self.assertIn("Error", result)
        self.assertIn("not found", result)
