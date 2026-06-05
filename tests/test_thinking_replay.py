from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from clearink.message import (
    content_block_to_dict,
    sanitize_messages_for_no_thinking,
)
from clearink.user.interface import _extract_response


class FakeResponse:
    def __init__(self, stop_reason: str, content: list) -> None:
        self.stop_reason = stop_reason
        self.content = content


class ThinkingReplayTests(unittest.TestCase):
    def test_content_block_preserves_deepseek_thinking_fields(self) -> None:
        block = SimpleNamespace(
            type="thinking",
            thinking="internal reasoning",
            provider="deepseek",
            marker={"effort": "max"},
        )

        self.assertEqual(
            content_block_to_dict(block),
            {
                "type": "thinking",
                "thinking": "internal reasoning",
                "provider": "deepseek",
                "marker": {"effort": "max"},
            },
        )

    def test_extract_response_reads_text_blocks_only(self) -> None:
        messages = [{
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "hidden"},
                {"type": "text", "text": "visible answer"},
            ],
        }]

        self.assertEqual(_extract_response(messages), "visible answer")

    def test_sanitize_messages_removes_thinking_without_mutating(self) -> None:
        messages = [{
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "hidden"},
                {"type": "text", "text": "visible"},
            ],
        }]

        clean = sanitize_messages_for_no_thinking(messages)
        clean[0]["content"][0]["text"] = "changed"

        self.assertEqual(
            clean,
            [{"role": "assistant", "content": [{"type": "text", "text": "changed"}]}],
        )
        self.assertEqual(messages[0]["content"][0]["thinking"], "hidden")
        self.assertEqual(messages[0]["content"][1]["text"], "visible")

    def test_agent_loop_replays_full_thinking_assistant_message(self) -> None:
        import clearink.main as main_module

        api_messages: list[list[dict]] = []

        def fake_safe_api_call(_client, **kwargs):
            api_messages.append(copy.deepcopy(kwargs["messages"]))
            if len(api_messages) == 1:
                return (
                    FakeResponse(
                        "tool_use",
                        [
                            SimpleNamespace(
                                type="thinking",
                                thinking="deepseek hidden",
                                provider="deepseek",
                            ),
                            SimpleNamespace(type="text", text="I will look this up."),
                            SimpleNamespace(
                                type="tool_use",
                                id="toolu_1",
                                name="lookup",
                                input={"query": "paper"},
                            ),
                        ],
                    ),
                    kwargs["messages"],
                    kwargs["compact_round"],
                )
            return (
                FakeResponse("end_turn", [SimpleNamespace(type="text", text="done")]),
                kwargs["messages"],
                kwargs["compact_round"],
            )

        with (
            patch.object(main_module, "_get_model", return_value="deepseek-v4-pro"),
            patch.object(main_module, "_get_client", return_value=object()),
            patch.object(main_module, "safe_api_call", side_effect=fake_safe_api_call),
            patch.object(main_module, "get_system_prompt", return_value="system"),
            patch.object(main_module, "load_memories", return_value=""),
            patch.object(main_module, "extract_memories", return_value=[]),
            patch.object(main_module, "run_hooks"),
            patch.object(main_module.background, "collect_background_results", return_value=[]),
            patch.object(main_module.background, "should_run_background", return_value=False),
            patch.object(
                main_module.background,
                "strip_runtime_control_args",
                side_effect=lambda args: args,
            ),
            patch.object(main_module.team, "collect_teammate_messages", return_value=[]),
            patch.dict(
                main_module.TOOL_HANDLERS,
                {"lookup": lambda query: "tool answer"},
                clear=True,
            ),
        ):
            messages = main_module.agent_loop([{"role": "user", "content": "question"}])

        self.assertEqual(len(api_messages), 2)
        second_call_messages = api_messages[1]
        assistant_messages = [
            msg for msg in second_call_messages
            if msg.get("role") == "assistant"
        ]
        self.assertEqual(len(assistant_messages), 1)
        self.assertEqual(
            [block["type"] for block in assistant_messages[0]["content"]],
            ["thinking", "text", "tool_use"],
        )
        self.assertEqual(
            assistant_messages[0]["content"][0],
            {
                "type": "thinking",
                "thinking": "deepseek hidden",
                "provider": "deepseek",
            },
        )
        self.assertEqual(
            second_call_messages[-1],
            {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": "tool answer",
                }],
            },
        )
        self.assertEqual(_extract_response(messages), "done")


if __name__ == "__main__":
    unittest.main()
