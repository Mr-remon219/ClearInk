from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


class FakeResponse:
    def __init__(self, stop_reason: str, content: list) -> None:
        self.stop_reason = stop_reason
        self.content = content


def test_build_extra_body_includes_deepseek_max_effort(monkeypatch) -> None:
    import clearink.main as main_module

    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.deepseek.example")
    monkeypatch.setenv("THINKING_EFFORT", "max")

    assert main_module._build_extra_body() == {
        "output_config": {"effort": "max"},
    }


def test_build_extra_body_skips_non_deepseek_base_url(monkeypatch) -> None:
    import clearink.main as main_module

    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    monkeypatch.setenv("THINKING_EFFORT", "max")

    assert main_module._build_extra_body() == {}


def test_agent_loop_passes_deepseek_model_and_extra_body(monkeypatch) -> None:
    import clearink.main as main_module

    captured_kwargs: list[dict] = []

    def fake_safe_api_call(_client, **kwargs):
        captured_kwargs.append(kwargs)
        return (
            FakeResponse(
                "end_turn",
                [SimpleNamespace(type="text", text="DeepSeek answer")],
            ),
            kwargs["messages"],
            kwargs["compact_round"],
        )

    monkeypatch.setenv("MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.deepseek.example")
    monkeypatch.setenv("THINKING_TYPE", "disabled")
    monkeypatch.setenv("THINKING_EFFORT", "max")

    with (
        patch.object(main_module, "_get_client", return_value=object()),
        patch.object(main_module, "safe_api_call", side_effect=fake_safe_api_call),
        patch.object(main_module, "get_system_prompt", return_value="system"),
        patch.object(main_module, "load_memories", return_value=""),
        patch.object(main_module, "extract_memories", return_value=[]),
        patch.object(main_module, "assemble_tool_pool", return_value=([], {})),
        patch.object(main_module, "run_hooks"),
        patch.object(
            main_module.background,
            "collect_background_results",
            return_value=[],
        ),
        patch.object(main_module.team, "collect_teammate_messages", return_value=[]),
    ):
        messages = main_module.agent_loop([
            {"role": "user", "content": "Use DeepSeek-compatible endpoint"},
        ])

    assert messages[-1]["role"] == "assistant"
    assert captured_kwargs[0]["model"] == "deepseek-v4-pro"
    assert captured_kwargs[0]["extra_body"] == {
        "output_config": {"effort": "max"},
    }
