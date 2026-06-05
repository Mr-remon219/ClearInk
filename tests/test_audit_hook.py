from __future__ import annotations

import importlib
import json

import pytest


@pytest.fixture
def reloaded_audit():
    from clearink.hook.hook import HOOKS
    import clearink.hook.audit as audit_mod

    original_hooks = {hook_type: list(handlers) for hook_type, handlers in HOOKS.items()}
    for handlers in HOOKS.values():
        handlers[:] = [
            entry for entry in handlers
            if entry.get("name") != "audit_log"
        ]
    audit_mod = importlib.reload(audit_mod)

    yield audit_mod

    for hook_type, handlers in original_hooks.items():
        HOOKS[hook_type] = handlers


def test_audit_hook_registers_on_every_hook_type(reloaded_audit) -> None:
    from clearink.hook.hook import HOOKS

    assert all(
        any(
            entry.get("name") == "audit_log" and entry.get("priority") == 999
            for entry in handlers
        )
        for handlers in HOOKS.values()
    )


def test_audit_jsonl_filters_payload_and_summarizes_hook_context(
    reloaded_audit,
    monkeypatch,
    tmp_path,
) -> None:
    from clearink.hook.hook import run_hooks

    audit_path = tmp_path / "logs" / "audit.jsonl"
    monkeypatch.setattr(reloaded_audit, "_AUDIT_PATH", audit_path)

    run_hooks("posttooluse", {
        "tool_name": "read_file",
        "arguments": {"file_path": "paper.pdf"},
        "messages": [{"role": "user", "content": "hidden from audit"}],
        "_private": "hidden",
        "unserializable": object(),
        "hook_context": {
            "current_paper": {"name": "Attention"},
            "papers_accessed": [{"path": "a.pdf"}, {"path": "b.pdf"}],
            "citation_requested": True,
        },
    })

    entry = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])

    assert entry["hook"] == "posttooluse"
    assert entry["data"]["tool_name"] == "read_file"
    assert entry["data"]["arguments"] == {"file_path": "paper.pdf"}
    assert "messages" not in entry["data"]
    assert "_private" not in entry["data"]
    assert "object object" in entry["data"]["unserializable"]
    assert entry["data"]["hc"] == {
        "paper": "Attention",
        "papers_count": 2,
        "citation": True,
    }
