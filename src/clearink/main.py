from anthropic import Anthropic
from dotenv import load_dotenv
from datetime import datetime
import os

from .config import ENV_PATH
from .tool.register import TOOL, TOOL_HANDLERS
from .tool import basetool, skill, todo, subagent  # noqa: F401 — side-effect: registers tools
from .hook import run_hooks, hook_context
from .context_compact import CompactConfig, compact_messages, reactive_compact
from .context_compact.token_estimate import estimate_tokens

load_dotenv(ENV_PATH, override=True)
model = os.getenv("MODEL")
thinking_type = os.getenv("THINKING_TYPE")
thinking_effort = os.getenv("THINKING_EFFORT")
client = Anthropic()


def agent_loop(
    messages: list,
    system: str = "",
    compact_config: CompactConfig | None = None,
) -> list:
    turn_count = 0
    compact_round = 0
    config = compact_config or CompactConfig()
    if not config.session_id:
        config.session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
    last_compacted_turn = -1

    while True:
        run_hooks("userpromptsubmit", {
            "messages": messages,
            "hook_context": hook_context,
        })

        # Context compaction — once per turn, after hooks, before API call
        if turn_count > 0 and turn_count != last_compacted_turn:
            if turn_count % config.compact_interval_turns == 0:
                compact_round += 1
                messages = compact_messages(
                    messages, config, hook_context, compact_round,
                )

            if turn_count % config.reactive_interval_turns == 0:
                estimated = estimate_tokens(
                    messages, config.token_estimation_chars_per_token,
                )
                if estimated > config.reactive_trigger_tokens:
                    compact_round += 1
                    messages = reactive_compact(
                        messages, config, hook_context, compact_round,
                    )

            last_compacted_turn = turn_count

        try:
            response = client.messages.create(
                model=model,
                system=system,
                messages=messages,
                tools=TOOL,
                max_tokens=4096,
                thinking={"type": thinking_type},
                extra_body={"output_config": {"effort": thinking_effort}},
            )
        except Exception as e:
            print(f"[Error] API call failed: {e}")
            turn_count += 1
            continue

        if response.stop_reason == "end_turn":
            turn_count += 1
            run_hooks("stop", {
                "messages": messages,
                "turns": turn_count,
                "hook_context": hook_context,
            })
            return messages

        if response.stop_reason == "max_tokens":
            turn_count += 1
            # Append whatever text was generated so far and let the loop continue
            for content_block in response.content:
                if content_block.type == "text":
                    messages.append({"role": "assistant", "content": content_block.text})
            continue

        for content_block in response.content:
            if content_block.type == "text":
                messages.append({"role": "assistant", "content": content_block.text})
            elif content_block.type == "tool_use":
                tool_name = content_block.name
                tool_args = content_block.input

                run_hooks("pretooluse", {
                    "tool_name": tool_name,
                    "arguments": tool_args,
                    "hook_context": hook_context,
                })

                handler = TOOL_HANDLERS.get(tool_name)
                try:
                    result = handler(**tool_args) if handler else f"Unknown tool: {tool_name}"
                    error = None
                except Exception as e:
                    result = None
                    error = str(e)

                run_hooks("posttooluse", {
                    "tool_name": tool_name,
                    "arguments": tool_args,
                    "result": result,
                    "error": error,
                    "hook_context": hook_context,
                })

                messages.append({
                    "role": "assistant",
                    "content": [content_block],
                })
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": result or error or "",
                    }],
                })


def main():
    from .system_build import system_build
    system_msg = system_build()
    messages = []
    agent_loop(messages, system=system_msg)
