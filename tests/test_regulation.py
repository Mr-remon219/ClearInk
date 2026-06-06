"""Tests for the Regulation module (tracker + tools)."""

from __future__ import annotations

import time
import unittest

from clearink.tool.team.tracker import ExecutionTracker


class TestExecutionTracker(unittest.TestCase):
    """Tests for the ExecutionTracker class."""

    def setUp(self):
        self.tracker = ExecutionTracker()

    def test_record_assignment_creates_entry(self):
        """record_assignment creates a working entry."""
        self.tracker.record_assignment("alice", "1")
        status = self.tracker.get_teammate_status("alice")
        self.assertIsNotNone(status)
        self.assertEqual(status["task_id"], "1")
        self.assertEqual(status["status"], "working")

    def test_record_completion_updates_status(self):
        """record_completion marks the entry as completed."""
        self.tracker.record_assignment("bob", "2")
        self.tracker.record_completion("bob")
        status = self.tracker.get_teammate_status("bob")
        self.assertEqual(status["status"], "completed")

    def test_record_rejection_preserved_in_rejections(self):
        """Rejection record survives reassignment of the same teammate."""
        self.tracker.record_assignment("carol", "3")
        self.tracker.record_rejection("3", "carol", "incomplete output")

        # Rejection record indexed by task_id
        tr = self.tracker.get_task_record("3")
        self.assertIsNotNone(tr)
        self.assertEqual(tr["status"], "rejected")
        self.assertEqual(tr["from_teammate"], "carol")
        self.assertEqual(tr["reason"], "incomplete output")

        # Teammate status also updated
        status = self.tracker.get_teammate_status("carol")
        self.assertEqual(status["status"], "rejected")

    def test_rejection_record_survives_new_assignment(self):
        """Rejection record in _rejections not overwritten by new assignment."""
        self.tracker.record_assignment("dave", "4")
        self.tracker.record_rejection("4", "dave", "bad")

        # Assign dave to a new task
        self.tracker.record_assignment("dave", "5")

        # Old task's rejection record should still exist
        tr = self.tracker.get_task_record("4")
        self.assertIsNotNone(tr)
        self.assertEqual(tr["status"], "rejected")

        # New task should show working
        status = self.tracker.get_teammate_status("dave")
        self.assertEqual(status["task_id"], "5")
        self.assertEqual(status["status"], "working")

    def test_record_removal_clears_entry(self):
        """record_removal removes teammate from active tracking."""
        self.tracker.record_assignment("eve", "6")
        self.tracker.record_removal("eve")
        status = self.tracker.get_teammate_status("eve")
        self.assertIsNone(status)

    def test_get_all_active_returns_copy(self):
        """get_all_active returns a dict of current assignments."""
        self.tracker.record_assignment("frank", "7")
        self.tracker.record_assignment("grace", "8")
        active = self.tracker.get_all_active()
        self.assertEqual(len(active), 2)
        self.assertIn("frank", active)
        self.assertIn("grace", active)

    def test_get_teammate_by_task_reverse_lookup(self):
        """get_teammate_by_task finds the teammate assigned to a task."""
        self.tracker.record_assignment("heidi", "9")
        found = self.tracker.get_teammate_by_task("9")
        self.assertEqual(found, "heidi")

        not_found = self.tracker.get_teammate_by_task("99")
        self.assertIsNone(not_found)

    def test_get_task_record_returns_none_for_unknown(self):
        """get_task_record returns None for tasks never tracked."""
        tr = self.tracker.get_task_record("nonexistent")
        self.assertIsNone(tr)

    def test_get_teammate_status_returns_none_for_unknown(self):
        """get_teammate_status returns None for unknown teammates."""
        status = self.tracker.get_teammate_status("ghost")
        self.assertIsNone(status)

    def test_start_time_is_recorded(self):
        """start_time is set to approximately now on assignment."""
        before = time.time()
        self.tracker.record_assignment("ivan", "10")
        after = time.time()
        status = self.tracker.get_teammate_status("ivan")
        self.assertGreaterEqual(status["start_time"], before)
        self.assertLessEqual(status["start_time"], after + 0.1)
