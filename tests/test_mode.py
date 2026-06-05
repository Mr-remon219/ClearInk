from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import clearink.user.mode as mode_mod


class TestModeCommandDetection(unittest.TestCase):
    """Test detect_mode_command for various input patterns."""

    def test_mode_1_command(self) -> None:
        self.assertEqual(mode_mod.detect_mode_command("/mode 1"), 1)

    def test_mode_2_command(self) -> None:
        self.assertEqual(mode_mod.detect_mode_command("/mode 2"), 2)

    def test_regular_message_returns_none(self) -> None:
        self.assertIsNone(mode_mod.detect_mode_command("hello"))
        self.assertIsNone(mode_mod.detect_mode_command("What is this paper about?"))

    def test_case_insensitive(self) -> None:
        self.assertEqual(mode_mod.detect_mode_command("/MODE 1"), 1)
        self.assertEqual(mode_mod.detect_mode_command("/Mode 2"), 2)

    def test_trailing_spaces(self) -> None:
        self.assertEqual(mode_mod.detect_mode_command("  /mode 1  "), 1)
        self.assertEqual(mode_mod.detect_mode_command("/mode 2   "), 2)

    def test_invalid_mode_number_returns_none(self) -> None:
        self.assertIsNone(mode_mod.detect_mode_command("/mode 3"))
        self.assertIsNone(mode_mod.detect_mode_command("/mode 0"))
        self.assertIsNone(mode_mod.detect_mode_command("/mode -1"))

    def test_extra_text_returns_none(self) -> None:
        """Extra text after /mode N should not match the strict regex."""
        self.assertIsNone(mode_mod.detect_mode_command("/mode 1 please"))
        self.assertIsNone(mode_mod.detect_mode_command("/mode 2 now"))


class TestModeSetAndGet(unittest.TestCase):
    """Test set_mode and get_mode with global state management."""

    _orig_mode: int
    _orig_step_mode: bool

    def setUp(self) -> None:
        self._orig_mode = mode_mod._current_mode
        self._orig_step_mode = mode_mod._step_mode

    def tearDown(self) -> None:
        mode_mod._current_mode = self._orig_mode
        mode_mod._step_mode = self._orig_step_mode

    def test_default_mode_is_1(self) -> None:
        self.assertEqual(mode_mod.get_mode(), 1)

    def test_set_mode_1_then_get(self) -> None:
        mode_mod.set_mode(1)
        self.assertEqual(mode_mod.get_mode(), 1)

    def test_set_mode_2_then_get(self) -> None:
        mode_mod.set_mode(2)
        self.assertEqual(mode_mod.get_mode(), 2)

    def test_set_invalid_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            mode_mod.set_mode(99)
        with self.assertRaises(ValueError):
            mode_mod.set_mode(0)
        with self.assertRaises(ValueError):
            mode_mod.set_mode(-1)

    def test_set_mode_invalid_leaves_current_unchanged(self) -> None:
        mode_mod.set_mode(1)
        with self.assertRaises(ValueError):
            mode_mod.set_mode(99)
        self.assertEqual(mode_mod.get_mode(), 1)

    def test_set_same_mode_is_noop_for_hooks(self) -> None:
        mode_mod._current_mode = 1
        with patch.object(mode_mod, "run_hooks") as mock_run_hooks:
            mode_mod.set_mode(1)
        self.assertEqual(mode_mod.get_mode(), 1)
        mock_run_hooks.assert_not_called()


class TestBuildQueryForMode(unittest.TestCase):
    _orig_mode: int

    def setUp(self) -> None:
        self._orig_mode = mode_mod._current_mode

    def tearDown(self) -> None:
        mode_mod._current_mode = self._orig_mode

    def test_builds_mode_1_query_without_mutating_current_mode(self) -> None:
        mode_mod._current_mode = 2
        query = mode_mod.build_query_for_mode("Paper A", "Eq. 1", 1)

        self.assertEqual(mode_mod.get_mode(), 2)
        self.assertIn("[Mode 1 instructions begin]", query)
        self.assertIn("Formula: Eq. 1", query)

    def test_builds_mode_2_query_without_mutating_current_mode(self) -> None:
        mode_mod._current_mode = 1
        query = mode_mod.build_query_for_mode("Paper B", "What is the claim?", 2)

        self.assertEqual(mode_mod.get_mode(), 1)
        self.assertIn("[Mode 2 instructions begin]", query)
        self.assertIn("Question: What is the claim?", query)

    def test_build_query_for_mode_rejects_invalid_mode(self) -> None:
        with self.assertRaises(ValueError):
            mode_mod.build_query_for_mode("Paper", "x", 99)


class TestStepMode(unittest.TestCase):
    """Test step mode toggle."""

    _orig_step_mode: bool

    def setUp(self) -> None:
        self._orig_step_mode = mode_mod._step_mode

    def tearDown(self) -> None:
        mode_mod._step_mode = self._orig_step_mode

    def test_default_step_mode_is_false(self) -> None:
        self.assertFalse(mode_mod.is_step_mode())

    def test_set_step_mode_true(self) -> None:
        mode_mod.set_step_mode(True)
        self.assertTrue(mode_mod.is_step_mode())

    def test_set_step_mode_false(self) -> None:
        mode_mod.set_step_mode(True)
        mode_mod.set_step_mode(False)
        self.assertFalse(mode_mod.is_step_mode())

    def test_set_step_mode_toggle(self) -> None:
        mode_mod.set_step_mode(True)
        self.assertTrue(mode_mod.is_step_mode())
        mode_mod.set_step_mode(False)
        self.assertFalse(mode_mod.is_step_mode())


class TestBuildStepInstructions(unittest.TestCase):
    """Test build_step_instructions content."""

    def test_contains_step_sections(self) -> None:
        instructions = mode_mod.build_step_instructions()
        self.assertIn("Step 1", instructions)
        self.assertIn("Step 2", instructions)
        self.assertIn("Step 3+", instructions)

    def test_contains_step_navigation_commands(self) -> None:
        instructions = mode_mod.build_step_instructions()
        self.assertIn("/next", instructions)
        self.assertIn("/end", instructions)

    def test_contains_send_marker(self) -> None:
        instructions = mode_mod.build_step_instructions()
        self.assertIn("[发送", instructions)

    def test_is_non_empty_string(self) -> None:
        instructions = mode_mod.build_step_instructions()
        self.assertIsInstance(instructions, str)
        self.assertTrue(len(instructions) > 0)


class TestModeLabelsAndHints(unittest.TestCase):
    """Test mode label, switch hint, and input prompt."""

    _orig_mode: int

    def setUp(self) -> None:
        self._orig_mode = mode_mod._current_mode

    def tearDown(self) -> None:
        mode_mod._current_mode = self._orig_mode

    def test_get_mode_label_mode_1(self) -> None:
        mode_mod._current_mode = 1
        self.assertEqual(mode_mod.get_mode_label(), "Formula Analysis")

    def test_get_mode_label_mode_2(self) -> None:
        mode_mod._current_mode = 2
        self.assertEqual(mode_mod.get_mode_label(), "Paper Q&A")

    def test_get_mode_label_unknown(self) -> None:
        mode_mod._current_mode = 99
        self.assertEqual(mode_mod.get_mode_label(), "Unknown")

    def test_get_switch_hint_from_mode_1(self) -> None:
        mode_mod._current_mode = 1
        self.assertEqual(mode_mod.get_switch_hint(), "/mode 2 to switch")

    def test_get_switch_hint_from_mode_2(self) -> None:
        mode_mod._current_mode = 2
        self.assertEqual(mode_mod.get_switch_hint(), "/mode 1 to switch")

    def test_second_input_prompt_mode_1(self) -> None:
        mode_mod._current_mode = 1
        self.assertEqual(
            mode_mod.get_second_input_prompt(), "Formula number or description"
        )

    def test_second_input_prompt_mode_2(self) -> None:
        mode_mod._current_mode = 2
        self.assertEqual(
            mode_mod.get_second_input_prompt(), "Your question about the paper"
        )


class TestModePromptFallback(unittest.TestCase):
    def test_mode_1_fallback_when_prompt_file_missing(self) -> None:
        original_prompts_dir = mode_mod._PROMPTS_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                mode_mod._PROMPTS_DIR = Path(tmp)
                prompt = mode_mod.get_mode_prompt(1)
        finally:
            mode_mod._PROMPTS_DIR = original_prompts_dir

        self.assertIn("Mode 1", prompt)
        self.assertIn("Formula Dependency Analysis", prompt)

    def test_mode_2_fallback_when_prompt_file_missing(self) -> None:
        original_prompts_dir = mode_mod._PROMPTS_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                mode_mod._PROMPTS_DIR = Path(tmp)
                prompt = mode_mod.get_mode_prompt(2)
        finally:
            mode_mod._PROMPTS_DIR = original_prompts_dir

        self.assertIn("Mode 2", prompt)
        self.assertIn("Paper Content Q&A", prompt)


if __name__ == "__main__":
    unittest.main()
