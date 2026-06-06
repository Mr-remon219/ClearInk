from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


@pytest.fixture
def api_state(monkeypatch, tmp_data_dir):
    import clearink.api.session as session_mod
    import clearink.user.mode as mode_mod

    mgr = session_mod.SessionManager()
    monkeypatch.setattr(session_mod, "_session_manager", mgr)
    monkeypatch.setattr(mode_mod, "_PROMPTS_DIR", tmp_data_dir / "system_prompts")
    # run_hooks removed from session/endpoints — hook types (session_created, etc.) deleted
    mode_mod.set_mode(1)
    mode_mod.set_step_mode(False)
    return mgr


def _assert_json_response(result: dict) -> None:
    json.dumps(result, ensure_ascii=False)
    assert isinstance(result["ok"], bool)


def test_api_exports_are_django_view_friendly() -> None:
    import clearink.api as api

    for name in [
        "query",
        "followup",
        "step_next",
        "step_end",
        "set_mode",
        "set_step_mode",
        "get_session_info",
        "delete_session",
    ]:
        assert callable(getattr(api, name))
        assert name in api.__all__


def test_api_import_does_not_load_main_runtime() -> None:
    src_path = Path(__file__).resolve().parents[1] / "src"
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(src_path)!r}); "
        "import clearink.api; "
        "loaded = {'clearink.main', 'clearink.user.interface'} & set(sys.modules); "
        "raise SystemExit(1 if loaded else 0)"
    )

    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def test_query_followup_step_and_session_lifecycle(api_state, monkeypatch) -> None:
    import clearink.api.endpoints as endpoints
    import clearink.user.mode as mode_mod

    agent_inputs: list[list[dict]] = []
    mode_events: list[tuple[int, int]] = []

    def fake_agent_loop(messages: list[dict]) -> list[dict]:
        agent_inputs.append([dict(msg) for msg in messages])
        return messages + [{
            "role": "assistant",
            "content": [{"type": "text", "text": "Answer <b> with $E=mc^2$"}],
        }]

    monkeypatch.setattr(endpoints, "agent_loop", fake_agent_loop)
    monkeypatch.setattr(
        mode_mod,
        "run_hooks",
        lambda hook_type, context: mode_events.append(
            (context["old_mode"], context["new_mode"])
        ) if hook_type == "mode_switched" else None,
    )
    mode_mod.set_mode(1)

    first = endpoints.query(
        paper="Attention Is All You Need",
        second_input="What is self-attention?",
        mode=2,
        session_id="django-session",
    )
    _assert_json_response(first)
    assert first["ok"] is True
    assert first["session_id"] == "django-session"
    assert "&lt;b&gt;" in first["response"]
    assert "$E=mc^2$" in first["response"]
    assert api_state.get("django-session").mode == 2
    assert mode_mod.get_mode() == 1
    assert mode_events == []
    assert "Question: What is self-attention?" in agent_inputs[0][0]["content"]

    step_on = endpoints.set_step_mode(True, "django-session")
    _assert_json_response(step_on)
    assert step_on["step_mode"] is True

    follow = endpoints.followup("Continue with details", "django-session")
    _assert_json_response(follow)
    assert follow["ok"] is True
    assert follow["step_mode"] is True
    followup_content = agent_inputs[1][-1]["content"]
    assert "**Step 1" in followup_content
    assert "[Mode 2 instructions begin]" in followup_content
    assert "Mode 2: Paper Q&A test mode." in followup_content
    assert "Continue with details" in followup_content
    assert mode_mod.get_current_step() == 0

    next_step = endpoints.step_next("django-session")
    _assert_json_response(next_step)
    assert next_step["ok"] is True
    assert "**Step 2" in agent_inputs[2][-1]["content"]
    assert mode_mod.get_current_step() == 0

    end = endpoints.step_end("django-session")
    _assert_json_response(end)
    assert end["ok"] is True
    assert len(agent_inputs) == 3

    switched = endpoints.set_mode(1, "django-session")
    _assert_json_response(switched)
    assert switched["mode"] == 1

    info = endpoints.get_session_info("django-session")
    _assert_json_response(info)
    assert info["mode"] == 1
    assert info["step_mode"] is True
    assert info["messages_count"] == len(api_state.get("django-session").messages)

    deleted = endpoints.delete_session("django-session")
    _assert_json_response(deleted)
    assert deleted["ok"] is True
    assert api_state.get("django-session") is None


def test_query_resets_existing_session_in_place(api_state, monkeypatch) -> None:
    import clearink.api.endpoints as endpoints

    existing = api_state.create("reset-session")
    existing.messages = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "old answer"},
    ]
    existing.step_mode = True

    def fake_agent_loop(messages: list[dict]) -> list[dict]:
        return messages + [{"role": "assistant", "content": "fresh answer"}]

    monkeypatch.setattr(endpoints, "agent_loop", fake_agent_loop)

    result = endpoints.query(
        "Fresh Paper",
        "Fresh question",
        mode=2,
        session_id="reset-session",
    )

    _assert_json_response(result)
    assert result["ok"] is True
    assert api_state.get("reset-session") is existing
    assert existing.mode == 2
    assert len(existing.messages) == 2
    assert existing.messages[-1]["content"] == "fresh answer"
    assert "old answer" not in json.dumps(existing.messages)


def test_followup_requests_are_serialized_per_session(
    api_state,
    monkeypatch,
) -> None:
    import clearink.api.endpoints as endpoints

    api_state.create("shared-session")
    active_calls = 0
    max_active_calls = 0
    active_lock = threading.Lock()
    barrier = threading.Barrier(3, timeout=5)
    results: dict[int, dict] = {}
    errors: list[BaseException] = []

    def fake_agent_loop(messages: list[dict]) -> list[dict]:
        nonlocal active_calls, max_active_calls
        with active_lock:
            active_calls += 1
            max_active_calls = max(max_active_calls, active_calls)
        time.sleep(0.02)
        with active_lock:
            active_calls -= 1
        return messages + [{"role": "assistant", "content": "ok"}]

    def worker(idx: int) -> None:
        try:
            barrier.wait()
            results[idx] = endpoints.followup(f"question {idx}", "shared-session")
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(endpoints, "agent_loop", fake_agent_loop)

    threads = [
        threading.Thread(target=worker, args=(0,)),
        threading.Thread(target=worker, args=(1,)),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)

    if errors:
        raise errors[0]

    assert {idx: result["ok"] for idx, result in results.items()} == {
        0: True,
        1: True,
    }
    assert max_active_calls == 1
    session = api_state.get("shared-session")
    assert session is not None
    assert [msg["role"] for msg in session.messages].count("user") == 2
    assert [msg["role"] for msg in session.messages].count("assistant") == 2


def test_api_missing_session_responses_are_json_serializable(api_state) -> None:
    import clearink.api.endpoints as endpoints

    for result in [
        endpoints.followup("hello", "missing"),
        endpoints.step_next("missing"),
        endpoints.step_end("missing"),
        endpoints.set_mode(2, "missing"),
        endpoints.set_step_mode(True, "missing"),
        endpoints.get_session_info("missing"),
        endpoints.delete_session("missing"),
    ]:
        _assert_json_response(result)
        assert result["ok"] is False
        assert "not found" in result["error"]


def test_query_invalid_mode_does_not_create_session(api_state) -> None:
    import clearink.api.endpoints as endpoints

    result = endpoints.query("paper", "question", mode=99, session_id="bad-mode")

    _assert_json_response(result)
    assert result == {"ok": False, "error": "Invalid mode: 99. Use 1 or 2."}
    assert api_state.get("bad-mode") is None


def test_query_preserves_global_mode_when_build_query_raises(
    api_state,
    monkeypatch,
) -> None:
    import clearink.api.endpoints as endpoints
    import clearink.user.mode as mode_mod

    mode_mod.set_mode(1)
    monkeypatch.setattr(
        endpoints.mode_mod,
        "build_query_for_mode",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = endpoints.query("paper", "question", mode=2, session_id="s1")

    _assert_json_response(result)
    assert result == {"ok": False, "error": "boom"}
    assert mode_mod.get_mode() == 1
