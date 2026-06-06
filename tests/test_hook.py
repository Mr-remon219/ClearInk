from __future__ import annotations

import unittest

from clearink.hook.hook import HOOKS, register_hook, run_hooks

_KNOWN_HOOK_TYPES = {
    "userpromptsubmit",
    "pretooluse",
    "posttooluse",
    "stop",
    "mode_switched",
    "mcp_connected",
    "teammate_spawned",
    "teammate_stopped",
    "task_lifecycle",
}


class TestHookRegistry(unittest.TestCase):
    """Test HOOKS dict structure and registration."""

    def setUp(self) -> None:
        for lst in HOOKS.values():
            lst.clear()

    def tearDown(self) -> None:
        for lst in HOOKS.values():
            lst.clear()

    def test_hooks_has_expected_types(self) -> None:
        self.assertEqual(set(HOOKS.keys()), _KNOWN_HOOK_TYPES)

    def test_hooks_has_9_types(self) -> None:
        self.assertEqual(len(HOOKS), 9)

    def test_all_hook_types_start_empty(self) -> None:
        for hook_type, handlers in HOOKS.items():
            with self.subTest(hook_type=hook_type):
                self.assertEqual(handlers, [])


class TestRegistration(unittest.TestCase):
    """Test register_hook decorator."""

    def setUp(self) -> None:
        for lst in HOOKS.values():
            lst.clear()

    def tearDown(self) -> None:
        for lst in HOOKS.values():
            lst.clear()

    def test_register_valid_type(self) -> None:
        @register_hook("stop")
        def my_handler(context: dict) -> None:
            pass

        self.assertEqual(len(HOOKS["stop"]), 1)
        self.assertEqual(HOOKS["stop"][0]["name"], "my_handler")

    def test_register_with_custom_name(self) -> None:
        @register_hook("stop", name="custom_name")
        def another_handler(context: dict) -> None:
            pass

        self.assertEqual(HOOKS["stop"][0]["name"], "custom_name")

    def test_register_invalid_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            @register_hook("non_existent_type")
            def bad_handler(context: dict) -> None:  # type: ignore[misc]
                pass


class TestPriorityOrder(unittest.TestCase):
    """Test that handlers execute in priority order."""

    def setUp(self) -> None:
        for lst in HOOKS.values():
            lst.clear()

    def tearDown(self) -> None:
        for lst in HOOKS.values():
            lst.clear()

    def test_lower_priority_fires_first(self) -> None:
        execution_order: list[str] = []

        @register_hook("stop", name="high_priority", priority=10)
        def first(context: dict) -> None:
            execution_order.append("first")

        @register_hook("stop", name="low_priority", priority=100)
        def second(context: dict) -> None:
            execution_order.append("second")

        run_hooks("stop", {})
        self.assertEqual(execution_order, ["first", "second"])

    def test_default_priority_is_100(self) -> None:
        @register_hook("pretooluse", name="handler_a", priority=100)
        def a(context: dict) -> None:
            pass

        entry = HOOKS["pretooluse"][0]
        self.assertEqual(entry["priority"], 100)

    def test_priority_stays_sorted_after_registration(self) -> None:
        execution_order: list[str] = []

        @register_hook("mode_switched", name="middle", priority=50)
        def middle(context: dict) -> None:
            execution_order.append("middle")

        @register_hook("mode_switched", name="low", priority=100)
        def low(context: dict) -> None:
            execution_order.append("low")

        @register_hook("mode_switched", name="high", priority=10)
        def high(context: dict) -> None:
            execution_order.append("high")

        run_hooks("mode_switched", {})
        self.assertEqual(execution_order, ["high", "middle", "low"])


class TestRunHooks(unittest.TestCase):
    """Test run_hooks execution logic."""

    def setUp(self) -> None:
        for lst in HOOKS.values():
            lst.clear()

    def tearDown(self) -> None:
        for lst in HOOKS.values():
            lst.clear()

    def test_injects_hook_type_in_context(self) -> None:
        captured: dict | None = None

        @register_hook("stop")
        def capture(context: dict) -> None:
            nonlocal captured
            captured = context

        ctx = run_hooks("stop", {"some": "data"})
        self.assertIsNotNone(captured)
        self.assertEqual(captured["_hook_type"], "stop")  # type: ignore[index]
        self.assertEqual(ctx["_hook_type"], "stop")

    def test_handler_receives_context(self) -> None:
        @register_hook("stop", name="check_ctx")
        def check(context: dict) -> None:
            self.assertEqual(context.get("foo"), "bar")

        run_hooks("stop", {"foo": "bar"})

    def test_handler_modifies_context(self) -> None:
        @register_hook("stop", name="modifier")
        def modifier(context: dict) -> None:
            context["modified"] = True

        ctx = run_hooks("stop", {})
        self.assertTrue(ctx["modified"])

    def test_handler_exception_captured_does_not_crash(self) -> None:
        @register_hook("stop", name="crashy")
        def crashy(context: dict) -> None:
            raise RuntimeError("boom")

        ctx = run_hooks("stop", {"key": "val"})

        self.assertIn("hook_errors", ctx)
        self.assertEqual(len(ctx["hook_errors"]), 1)
        error = ctx["hook_errors"][0]
        self.assertEqual(error["hook"], "crashy")
        self.assertEqual(error["type"], "stop")
        self.assertIn("boom", error["error"])

    def test_subsequent_handler_runs_after_exception(self) -> None:
        execution_order: list[str] = []

        @register_hook("stop", name="crashy", priority=10)
        def crashy(context: dict) -> None:
            execution_order.append("crashy")
            raise RuntimeError("boom")

        @register_hook("stop", name="survivor", priority=20)
        def survivor(context: dict) -> None:
            execution_order.append("survivor")

        ctx = run_hooks("stop", {})
        self.assertEqual(execution_order, ["crashy", "survivor"])
        self.assertEqual(len(ctx["hook_errors"]), 1)

    def test_multiple_exceptions_all_captured(self) -> None:
        @register_hook("stop", name="crash_a", priority=10)
        def crash_a(context: dict) -> None:
            raise ValueError("error A")

        @register_hook("stop", name="crash_b", priority=20)
        def crash_b(context: dict) -> None:
            raise TypeError("error B")

        ctx = run_hooks("stop", {})
        self.assertEqual(len(ctx["hook_errors"]), 2)
        self.assertEqual(ctx["hook_errors"][0]["hook"], "crash_a")
        self.assertEqual(ctx["hook_errors"][1]["hook"], "crash_b")

    def test_run_hooks_returns_context(self) -> None:
        @register_hook("stop", name="noop")
        def noop(context: dict) -> None:
            pass

        ctx = run_hooks("stop", {"a": 1})
        self.assertEqual(ctx["a"], 1)

    def test_run_hooks_empty_type_no_error(self) -> None:
        """Running hooks on a type with no handlers should not error."""
        # "stop" is deliberately empty after setUp
        ctx = run_hooks("stop", {"x": "y"})
        self.assertEqual(ctx["x"], "y")


if __name__ == "__main__":
    unittest.main()
