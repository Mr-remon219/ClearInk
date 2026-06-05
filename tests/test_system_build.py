"""Tests for clearink.system_prompt.system_build."""

from __future__ import annotations

import platform
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from clearink.system_prompt.system_build import (
    _build_context,
    _build_environment,
    _build_memory_index,
    set_current_memories,
)


class TestBuildEnvironment(unittest.TestCase):
    """Tests for _build_environment."""

    def test_contains_cwd_path(self):
        context = {"workspace": "/some/test/path"}
        result = _build_environment(context)
        self.assertIn("/some/test/path", result)

    def test_contains_os_name(self):
        context = {"workspace": "/tmp"}
        result = _build_environment(context)
        self.assertIn(platform.system(), result)

    def test_contains_current_date(self):
        context = {"workspace": "/tmp"}
        result = _build_environment(context)
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertIn(today, result)


class TestSetCurrentMemories(unittest.TestCase):
    """Tests for set_current_memories and its effect on _build_memory_index."""

    def setUp(self):
        # Save original state
        self._original = _build_context()["memories"]
        # Reset before each test
        set_current_memories("")

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.memory_dir = Path(self.tmp.name)
        (self.memory_dir / "MEMORY.md").write_text(
            "base memory content\n", encoding="utf-8"
        )

        patcher = patch(
            "clearink.system_prompt.system_build._MEMORY_DIR", self.memory_dir
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        set_current_memories(self._original)

    def test_sets_global(self):
        set_current_memories("custom text")
        self.assertEqual(_build_context()["memories"], "custom text")

    def test_subsequent_build_memory_index_includes_them(self):
        set_current_memories("custom memory line")
        context = _build_context()
        result = _build_memory_index(context)
        self.assertIn("custom memory line", result)
        self.assertIn("base memory content", result)


class TestBuildContext(unittest.TestCase):
    """Tests for _build_context."""

    def test_returns_dict_with_tools_key(self):
        with patch(
            "clearink.system_prompt.system_build.TOOL_HANDLERS",
            {"tool_a": lambda: None, "tool_b": lambda: None},
        ):
            result = _build_context()
            self.assertIn("enabled_tools", result)
            self.assertEqual(result["enabled_tools"], ["tool_a", "tool_b"])

    def test_returns_dict_with_workspace_key(self):
        with patch(
            "clearink.system_prompt.system_build.TOOL_HANDLERS", {}
        ):
            result = _build_context()
            self.assertIn("workspace", result)
            self.assertEqual(result["workspace"], str(Path.cwd()))
