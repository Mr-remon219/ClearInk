"""Tests for clearink.tool.background.core helpers."""

import unittest
from clearink.tool.background.core import (
    strip_runtime_control_args,
    is_slow_operation,
    should_run_background,
)


class TestStripRuntimeControlArgs(unittest.TestCase):
    """strip_runtime_control_args removes the run_in_background key."""

    def test_removes_run_in_background(self):
        original = {"command": "ls", "run_in_background": True, "timeout": 30}
        result = strip_runtime_control_args(original)
        self.assertNotIn("run_in_background", result)
        self.assertEqual(result["command"], "ls")
        self.assertEqual(result["timeout"], 30)

    def test_preserves_other_keys(self):
        original = {"command": "echo hi", "description": "say hi", "timeout": 10}
        result = strip_runtime_control_args(original)
        self.assertEqual(result, original)

    def test_empty_dict(self):
        result = strip_runtime_control_args({})
        self.assertEqual(result, {})

    def test_only_run_in_background(self):
        original = {"run_in_background": True}
        result = strip_runtime_control_args(original)
        self.assertEqual(result, {})

    def test_does_not_mutate_original(self):
        original = {"command": "ls", "run_in_background": True}
        copy_before = dict(original)
        strip_runtime_control_args(original)
        self.assertEqual(original, copy_before)


class TestIsSlowOperation(unittest.TestCase):
    """is_slow_operation identifies operations that should run in background."""

    # ── spawn_subagent (always True) ────────────────────────

    def test_spawn_subagent_always_slow(self):
        self.assertTrue(is_slow_operation("spawn_subagent", {}))

    # ── run_bash with pip install ───────────────────────────

    def test_run_bash_pip_install(self):
        self.assertTrue(is_slow_operation("run_bash", {"command": "pip install torch"}))

    def test_run_bash_pip3_install(self):
        self.assertTrue(is_slow_operation("run_bash", {"command": "pip3 install requests"}))

    def test_run_bash_uv_install(self):
        self.assertTrue(is_slow_operation("run_bash", {"command": "uv install numpy"}))

    def test_run_bash_npm_install(self):
        self.assertTrue(is_slow_operation("run_bash", {"command": "npm install react"}))

    def test_run_bash_git_clone(self):
        self.assertTrue(is_slow_operation("run_bash", {"command": "git clone https://example.com/repo.git"}))

    def test_run_bash_cargo_build(self):
        self.assertTrue(is_slow_operation("run_bash", {"command": "cargo build --release"}))

    # ── run_bash with large timeout ─────────────────────────

    def test_run_bash_large_timeout(self):
        self.assertTrue(is_slow_operation("run_bash", {"command": "echo hi", "timeout": 300}))

    def test_run_bash_timeout_exactly_120(self):
        self.assertFalse(is_slow_operation("run_bash", {"command": "echo hi", "timeout": 120}))

    def test_run_bash_timeout_just_above_120(self):
        self.assertTrue(is_slow_operation("run_bash", {"command": "echo hi", "timeout": 121}))

    # ── read_file with large limit ──────────────────────────

    def test_read_file_large_limit(self):
        self.assertTrue(is_slow_operation("read_file", {"file_path": "big.txt", "limit": 10000}))

    def test_read_file_limit_exactly_5000(self):
        self.assertFalse(is_slow_operation("read_file", {"file_path": "med.txt", "limit": 5000}))

    def test_read_file_limit_just_above_5000(self):
        self.assertTrue(is_slow_operation("read_file", {"file_path": "big.txt", "limit": 5001}))

    def test_read_file_no_limit(self):
        self.assertFalse(is_slow_operation("read_file", {"file_path": "small.txt"}))

    def test_read_file_limit_zero(self):
        self.assertFalse(is_slow_operation("read_file", {"file_path": "small.txt", "limit": 0}))

    def test_read_file_negative_limit(self):
        self.assertFalse(is_slow_operation("read_file", {"file_path": "x.txt", "limit": -1}))

    # ── normal run_bash (not slow) ──────────────────────────

    def test_run_bash_normal(self):
        self.assertFalse(is_slow_operation("run_bash", {"command": "ls -la", "timeout": 30}))

    def test_run_bash_ls(self):
        self.assertFalse(is_slow_operation("run_bash", {"command": "ls", "timeout": 10}))

    def test_run_bash_grep(self):
        self.assertFalse(is_slow_operation("run_bash", {"command": "grep pattern file.txt", "timeout": 30}))

    def test_unknown_tool_not_slow(self):
        self.assertFalse(is_slow_operation("some_tool", {}))

    # ── case insensitivity ─────────────────────────────────

    def test_run_bash_pip_install_case_insensitive(self):
        self.assertTrue(is_slow_operation("run_bash", {"command": "PIP INSTALL torch"}))

    # ── timeout as float ────────────────────────────────────

    def test_run_bash_timeout_float(self):
        self.assertTrue(is_slow_operation("run_bash", {"command": "echo hi", "timeout": 120.5}))


class TestShouldRunBackground(unittest.TestCase):
    """should_run_background checks run_in_background flag or delegates."""

    def test_run_in_background_true_returns_true(self):
        result = should_run_background("run_bash", {"command": "ls", "run_in_background": True})
        self.assertTrue(result)

    def test_run_in_background_false_delegates_to_is_slow(self):
        result = should_run_background(
            "run_bash",
            {"command": "pip install torch", "run_in_background": False},
        )
        self.assertTrue(result)

    def test_run_in_background_false_fast_operation(self):
        result = should_run_background(
            "run_bash",
            {"command": "ls", "run_in_background": False, "timeout": 10},
        )
        self.assertFalse(result)

    def test_run_in_background_missing_delegates_to_is_slow(self):
        self.assertTrue(
            should_run_background("spawn_subagent", {}),
        )
        self.assertFalse(
            should_run_background("run_bash", {"command": "echo hi", "timeout": 10}),
        )

    def test_unknown_tool_without_flag(self):
        self.assertFalse(
            should_run_background("unknown_tool", {"command": "hello"}),
        )
