"""Tests for clearink.tool.team.worktree.worktree internal helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clearink.tool.team.worktree.worktree import (
    _worktree_path,
    _branch_name,
    _load_bindings,
    _get_worktree_for_task,
)


class TestWorktreePath(unittest.TestCase):
    """Tests for _worktree_path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.worktrees_dir = Path(self.tmp.name)
        self.mailboxes_dir = self.worktrees_dir / ".mailboxes"

        patcher = patch.multiple(
            "clearink.tool.team.worktree.worktree",
            WORKTREES_DIR=self.worktrees_dir,
            MAILBOXES_DIR=self.mailboxes_dir,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_worktree_path_normal_name(self):
        """Normal name returns WORKTREES_DIR / name."""
        result = _worktree_path("my_worktree")
        self.assertEqual(result, self.worktrees_dir / "my_worktree")

    def test_worktree_path_mailboxes(self):
        """.mailboxes returns MAILBOXES_DIR."""
        result = _worktree_path(".mailboxes")
        self.assertEqual(result, self.mailboxes_dir)


class TestBranchName(unittest.TestCase):
    """Tests for _branch_name."""

    def test_branch_name_format(self):
        result = _branch_name("feature_x")
        self.assertEqual(result, "worktree/feature_x")


class TestLoadBindings(unittest.TestCase):
    """Tests for _load_bindings."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.worktrees_dir = Path(self.tmp.name)
        self.bindings_path = self.worktrees_dir / "bindings.json"

        patcher = patch.multiple(
            "clearink.tool.team.worktree.worktree",
            WORKTREES_DIR=self.worktrees_dir,
            BINDINGS_PATH=self.bindings_path,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_returns_empty_dict_when_file_missing(self):
        """No bindings file returns empty dict."""
        result = _load_bindings()
        self.assertEqual(result, {})

    def test_returns_parsed_dict_when_file_exists(self):
        """Valid bindings file returns parsed dict."""
        data = {"task1": "worktree_a", "task2": "worktree_b"}
        self.bindings_path.write_text(json.dumps(data), encoding="utf-8")
        result = _load_bindings()
        self.assertEqual(result, data)

    def test_returns_empty_dict_on_corrupt_json(self):
        """Corrupt JSON returns empty dict."""
        self.bindings_path.write_text("not valid json", encoding="utf-8")
        result = _load_bindings()
        self.assertEqual(result, {})


class TestGetWorktreeForTask(unittest.TestCase):
    """Tests for _get_worktree_for_task."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.worktrees_dir = Path(self.tmp.name)
        self.bindings_path = self.worktrees_dir / "bindings.json"

        patcher = patch.multiple(
            "clearink.tool.team.worktree.worktree",
            WORKTREES_DIR=self.worktrees_dir,
            BINDINGS_PATH=self.bindings_path,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_returns_worktree_name_when_binding_exists(self):
        """Returns worktree name when task_id is bound."""
        data = {"task42": "my_worktree"}
        self.bindings_path.write_text(json.dumps(data), encoding="utf-8")
        result = _get_worktree_for_task("task42")
        self.assertEqual(result, "my_worktree")

    def test_returns_none_when_not_found(self):
        """Returns None when task_id has no binding."""
        result = _get_worktree_for_task("nonexistent")
        self.assertIsNone(result)
