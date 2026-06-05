"""Integration tests for the ClearInk hook system.

Tests cover:
- All 14 hook types exist in HOOKS
- Hook registration and execution
- Lifecycle ordering (userpromptsubmit -> pretooluse -> posttooluse)
- Cross-hook context sharing via the shared context dict
- Exception isolation (one failing hook doesn't block others)
- Priority-based ordering within the same hook type
- Invalid hook type rejection
- _looks_like_paper detection heuristic
- detect_citation_request hook integration
- Audit hook JSONL logging
"""

from __future__ import annotations

import json

import pytest

from clearink.hook.hook import HOOKS, hook_context, register_hook, run_hooks
from clearink.hook.reading import _looks_like_paper
from tests.helpers import make_user_message, assert_jsonl_has


EXPECTED_HOOK_TYPES = frozenset({
    "userpromptsubmit",
    "pretooluse",
    "posttooluse",
    "stop",
    "session_created",
    "session_destroyed",
    "mode_switched",
    "step_mode_changed",
    "mcp_connected",
    "mcp_disconnected",
    "teammate_spawned",
    "teammate_stopped",
    "task_lifecycle",
    "api_request",
})


def test_all_hook_types_exist():
    """HOOKS should contain exactly the 14 expected types, each mapping to a list."""
    assert frozenset(HOOKS.keys()) == EXPECTED_HOOK_TYPES
    for hook_type in HOOKS:
        assert isinstance(HOOKS[hook_type], list), (
            f"Hook type {hook_type!r} should map to a list, "
            f"got {type(HOOKS[hook_type])}"
        )


def test_register_and_run_hook():
    """A registered userpromptsubmit handler should be invoked by run_hooks."""
    calls: list[str] = []

    @register_hook("userpromptsubmit", name="test_simple")
    def my_handler(context):
        calls.append("executed")

    run_hooks("userpromptsubmit", {"msg": "hello"})

    assert calls == ["executed"], f"Expected ['executed'], got {calls}"


def test_hook_lifecycle_order():
    """Hooks registered on different types should fire in call order."""
    order: list[str] = []

    @register_hook("userpromptsubmit", name="order_a", priority=100)
    def hook_a(ctx):
        order.append("userpromptsubmit")

    @register_hook("pretooluse", name="order_b", priority=100)
    def hook_b(ctx):
        order.append("pretooluse")

    @register_hook("posttooluse", name="order_c", priority=100)
    def hook_c(ctx):
        order.append("posttooluse")

    run_hooks("userpromptsubmit", {})
    run_hooks("pretooluse", {})
    run_hooks("posttooluse", {})

    assert order == ["userpromptsubmit", "pretooluse", "posttooluse"], (
        f"Expected lifecycle order, got {order}"
    )


def test_hook_context_cross_hook_sharing():
    """Data written to the context dict in one hook type should be readable
    in another.
    """

    @register_hook("pretooluse", name="share_set", priority=100)
    def setter(ctx):
        ctx["shared_data"] = "from_pretooluse"

    @register_hook("posttooluse", name="share_get", priority=100)
    def getter(ctx):
        ctx["readback"] = ctx.get("shared_data")

    ctx: dict = {}
    run_hooks("pretooluse", ctx)
    run_hooks("posttooluse", ctx)

    assert ctx.get("shared_data") == "from_pretooluse"
    assert ctx.get("readback") == "from_pretooluse"


def test_hook_exception_isolation():
    """A hook that raises should not prevent subsequent hooks from running,
    and the error should be captured in ``context["hook_errors"]``.
    """
    flag: list[str] = []

    @register_hook("userpromptsubmit", name="exploder", priority=100)
    def exploder(ctx):
        raise RuntimeError("test error")

    @register_hook("userpromptsubmit", name="raiser", priority=100)
    def raiser(ctx):
        flag.append("ok")

    context: dict = {}
    run_hooks("userpromptsubmit", context)

    assert flag == ["ok"], "Later hook should still execute after an error"
    assert "hook_errors" in context
    assert len(context["hook_errors"]) == 1
    err = context["hook_errors"][0]
    assert err["hook"] == "exploder"
    assert err["type"] == "userpromptsubmit"
    assert "test error" in err["error"]


def test_hook_priority_ordering():
    """Hooks on the same type should execute in ascending priority order."""
    execution: list[int] = []

    @register_hook("userpromptsubmit", name="p10", priority=10)
    def hp10(ctx):
        execution.append(10)

    @register_hook("userpromptsubmit", name="p5", priority=5)
    def hp5(ctx):
        execution.append(5)

    @register_hook("userpromptsubmit", name="p50", priority=50)
    def hp50(ctx):
        execution.append(50)

    run_hooks("userpromptsubmit", {})

    assert execution == [5, 10, 50], (
        f"Expected [5, 10, 50], got {execution}"
    )


def test_invalid_hook_type_raises():
    """register_hook on a nonexistent hook type should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown hook type"):

        @register_hook("nonexistent_type")
        def dummy(ctx):  # type: ignore[misc]
            pass


def test_looks_like_paper_detection():
    """_looks_like_paper should correctly identify paper-like file paths."""
    # Extension matches (.pdf, .txt, .md)
    assert _looks_like_paper("paper.pdf") is True
    assert _looks_like_paper("arxiv-2023.45678.txt") is True
    assert _looks_like_paper("paper-about-dogs.md") is True
    assert _looks_like_paper("README.md") is True

    # No match (no paper extension or keyword in stem)
    assert _looks_like_paper("main.py") is False
    assert _looks_like_paper("data.csv") is False

    # Keyword match in stem without matching extension
    assert _looks_like_paper("manuscript_final.docx") is True
    assert _looks_like_paper("chapter1.tex") is True


def test_detect_citation_request():
    """userpromptsubmit hooks should detect citation requests and set
    ``hook_context["citation_requested"]`` to True.
    """
    context = {
        "messages": [make_user_message("please cite the relevant papers")],
    }
    run_hooks("userpromptsubmit", context)

    hc = context.get("hook_context", {})
    assert hc.get("citation_requested") is True, (
        "citation_requested should be True after detecting a citation trigger"
    )
    # The hook uses context.setdefault("hook_context", hook_context), so the
    # value attached to context is the module-level hook_context singleton.
    assert hc is hook_context, (
        "context['hook_context'] should be the module-level hook_context object"
    )


def test_audit_hook_writes_jsonl(tmp_data_dir, monkeypatch):
    """The audit handler should write a valid JSONL entry after a hook event."""
    import clearink.hook.audit as audit_mod

    audit_path = tmp_data_dir / "logs" / "audit.jsonl"
    monkeypatch.setattr(audit_mod, "_AUDIT_PATH", audit_path)

    context = {
        "user_id": "test_user",
        "session_id": "sess-001",
        "messages": [make_user_message("What is formula (3.14)?")],
    }
    run_hooks("userpromptsubmit", context)

    # --- File existence & helper assertion --------------------------------
    assert audit_path.exists(), f"Audit file should exist at {audit_path}"
    assert_jsonl_has(audit_path, "hook", "userpromptsubmit")

    # --- Structural validation --------------------------------------------
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1, "Should have at least one audit line"
    entry = json.loads(lines[0])

    # Top-level fields
    assert "ts" in entry, "Audit entry missing 'ts'"
    assert isinstance(entry["ts"], (int, float)), "ts should be numeric"
    assert entry["hook"] == "userpromptsubmit"

    # Data sub-object
    assert "data" in entry, "Audit entry missing 'data'"
    # user_id is not a private or excluded key, so it should survive filtering
    assert entry["data"].get("user_id") == "test_user"

    # The audit handler explicitly filters out the "messages" key
    assert "messages" not in entry["data"], (
        "messages should be filtered out of audit data"
    )
    # Private keys (starting with '_') are also stripped
    assert "_hook_type" not in entry["data"], (
        "private keys should be filtered out of audit data"
    )
