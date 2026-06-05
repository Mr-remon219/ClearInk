"""Tests for clearink.tool.task_system.manager.TaskManager."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clearink.tool.task_system.manager import TaskManager


class TestTaskManager(unittest.TestCase):
    """TaskManager manages a DAG of tasks persisted to JSON files."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.tasks_dir = self.temp_dir / ".tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.patcher = patch(
            "clearink.tool.task_system.manager.TASKS_DIR",
            self.tasks_dir,
        )
        self.patcher.start()
        self.mgr = TaskManager()

    def tearDown(self):
        self.patcher.stop()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ── create_task ────────────────────────────────────────

    def test_create_task_returns_formatted_string(self):
        result = self.mgr.create_task("Write tests")
        self.assertIn("#1", result)
        # The icon for pending status is a space inside brackets
        self.assertIn("[ ]", result)
        self.assertIn("status: pending", result)

    def test_create_task_persists_to_disk(self):
        self.mgr.create_task("Persist me")
        task_file = self.tasks_dir / "1.json"
        self.assertTrue(task_file.exists())
        data = json.loads(task_file.read_text(encoding="utf-8"))
        self.assertEqual(data["subject"], "Persist me")
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["owner"], "")

    def test_create_task_auto_increments_id(self):
        self.mgr.create_task("first")
        self.mgr.create_task("second")
        self.mgr.create_task("third")
        self.assertEqual(len(self.mgr.list_tasks), 3)
        self.assertIn("1", self.mgr.list_tasks)
        self.assertIn("2", self.mgr.list_tasks)
        self.assertIn("3", self.mgr.list_tasks)

    def test_create_task_with_blockedBy_valid(self):
        self.mgr.create_task("prereq")
        result = self.mgr.create_task("dependent", blockedBy=["1"])
        self.assertIn("#2", result)

    def test_create_task_blockedBy_nonexistent_returns_error(self):
        result = self.mgr.create_task("orphan", blockedBy=["999"])
        self.assertIn("Error", result)
        self.assertIn("999", result)

    def test_create_task_with_description(self):
        result = self.mgr.create_task("described", description="some details")
        self.assertIn("#1", result)
        task = self.mgr.list_tasks["1"]
        self.assertEqual(task["description"], "some details")

    # ── can_start ──────────────────────────────────────────

    def test_can_start_pending_no_deps(self):
        self.mgr.create_task("standalone")
        self.assertTrue(self.mgr.can_start("1"))

    def test_can_start_pending_dep_not_completed(self):
        self.mgr.create_task("prereq", description="")
        self.mgr.create_task("dependent", blockedBy=["1"])
        self.assertFalse(self.mgr.can_start("2"))

    def test_can_start_completed_returns_false(self):
        self.mgr.create_task("task")
        self.mgr.claim_task("1")
        self.mgr.complete_task("1")
        self.assertFalse(self.mgr.can_start("1"))

    def test_can_start_nonexistent_task(self):
        self.assertFalse(self.mgr.can_start("999"))

    def test_can_start_pending_dep_completed(self):
        self.mgr.create_task("prereq")
        self.mgr.claim_task("1")
        self.mgr.complete_task("1")
        self.mgr.create_task("dependent", blockedBy=["1"])
        self.assertTrue(self.mgr.can_start("2"))

    # ── claim_task ─────────────────────────────────────────

    def test_claim_pending_sets_in_progress(self):
        self.mgr.create_task("claimable")
        result = self.mgr.claim_task("1", owner="Alice")
        self.assertIn("claimed", result.lower())
        task = self.mgr.list_tasks["1"]
        self.assertEqual(task["status"], "in_progress")
        self.assertEqual(task["owner"], "Alice")

    def test_claim_already_claimed_returns_error(self):
        self.mgr.create_task("mine")
        self.mgr.claim_task("1", owner="Alice")
        result = self.mgr.claim_task("1", owner="Bob")
        self.assertIn("Error", result)

    def test_claim_blocked_task_returns_error(self):
        self.mgr.create_task("prereq")
        self.mgr.create_task("blocked", blockedBy=["1"])
        result = self.mgr.claim_task("2", owner="Alice")
        self.assertIn("Error", result)
        self.assertIn("blocked", result)

    def test_claim_nonexistent_returns_error(self):
        result = self.mgr.claim_task("999")
        self.assertIn("Error", result)

    def test_claim_default_owner(self):
        self.mgr.create_task("default-owner")
        self.mgr.claim_task("1")
        task = self.mgr.list_tasks["1"]
        self.assertEqual(task["owner"], "agent")

    # ── complete_task ──────────────────────────────────────

    def test_complete_in_progress_sets_completed(self):
        self.mgr.create_task("finish-me")
        self.mgr.claim_task("1")
        result = self.mgr.complete_task("1")
        self.assertIn("completed", result.lower())

    def test_complete_nonexistent_returns_error(self):
        result = self.mgr.complete_task("999")
        self.assertIn("Error", result)

    def test_complete_not_in_progress_returns_error(self):
        self.mgr.create_task("never-started")
        result = self.mgr.complete_task("1")
        self.assertIn("Error", result)

    def test_complete_auto_unblocks_children(self):
        self.mgr.create_task("prereq")
        self.mgr.create_task("blocked", blockedBy=["1"])
        self.mgr.claim_task("1")
        result = self.mgr.complete_task("1")
        self.assertIn("Unblocked", result)
        self.assertIn("2", result)

    def test_complete_clears_owner(self):
        self.mgr.create_task("ownerless-after")
        self.mgr.claim_task("1", owner="Alice")
        self.mgr.complete_task("1")
        task = self.mgr.list_tasks["1"]
        self.assertEqual(task["owner"], "")

    # ── _refresh ───────────────────────────────────────────

    def test_refresh_picks_up_disk_changes(self):
        self.mgr.create_task("original")

        # Write a new task directly to disk (simulate another agent)
        new_task = {
            "id": "99",
            "subject": "from-disk",
            "status": "pending",
            "owner": "",
            "blockedBy": [],
            "blocks": [],
        }
        (self.tasks_dir / "99.json").write_text(
            json.dumps(new_task, indent=2), encoding="utf-8",
        )

        self.assertNotIn("99", self.mgr.list_tasks)
        self.mgr._refresh()
        self.assertIn("99", self.mgr.list_tasks)
        self.assertEqual(self.mgr.list_tasks["99"]["subject"], "from-disk")

    def test_refresh_removes_deleted_tasks(self):
        self.mgr.create_task("will-be-deleted")
        self.assertIn("1", self.mgr.list_tasks)

        (self.tasks_dir / "1.json").unlink()
        self.mgr._refresh()
        self.assertNotIn("1", self.mgr.list_tasks)

    # ── format_task_list ───────────────────────────────────

    def test_format_task_list_empty(self):
        mgr = TaskManager()
        self.assertEqual(mgr.format_task_list(), "(no tasks)")

    def test_format_task_list_shows_status_icons(self):
        self.mgr.create_task("pending-task")
        self.mgr.create_task("progress-task")
        self.mgr.claim_task("2")

        output = self.mgr.format_task_list()
        self.assertIn("#1", output)
        self.assertIn("#2", output)
        self.assertIn("pending-task", output)
        self.assertIn("progress-task", output)
        # in_progress icon is the Unicode arrow "→"
        self.assertIn("[→]", output)

    def test_format_task_list_sorted_by_id(self):
        self.mgr.create_task("second")
        self.mgr.create_task("first")
        lines = self.mgr.format_task_list().splitlines()
        self.assertIn("#1", lines[0])
        self.assertIn("#2", lines[1])
