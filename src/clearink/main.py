from anthropic import Anthropic
from dotenv import load_dotenv
from datetime import datetime
import os

from .config import ENV_PATH
from .tool.register import TOOL, TOOL_HANDLERS
from .tool import basetool, skill, todo, subagent, task_system, background, scheduler, teammate  # noqa: F401 — registers tools
from .hook import run_hooks, hook_context
from .system_prompt.memory_load import load_memories, extract_memories
from .system_prompt.memory_store import consolidate_memories
from .system_prompt.system_build import get_system_prompt
from .error_recovery.wrapper import safe_api_call
from .system_prompt import memory_tool  # noqa: F401 — registers save_memory tool
from .context_compact import CompactConfig, compact_messages, reactive_compact
from .context_compact.token_estimate import estimate_tokens

load_dotenv(ENV_PATH, override=True)
model = os.getenv("MODEL")
thinking_type = os.getenv("THINKING_TYPE")
thinking_budget = int(os.getenv("THINKING_BUDGET", "0") or "0")
base_url = os.getenv("ANTHROPIC_BASE_URL", "")
client = Anthropic()

def _build_thinking() -> dict:
    t = {"type": thinking_type}
    if thinking_type == "enabled" and thinking_budget > 0:
        t["budget_tokens"] = thinking_budget
    return t

def _build_extra_body() -> dict:
    body = {}
    effort = os.getenv("THINKING_EFFORT")
    if effort and "deepseek" in base_url.lower():
        body["output_config"] = {"effort": effort}
    return body


def agent_loop(
    messages: list,
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

        # Collect completed background task results
        for bg_result in background.collect_background_results():
            messages.append({"role": "user", "content": bg_result})

        # Context compaction — once per turn, after hooks, before API call
        if turn_count > 0 and turn_count != last_compacted_turn:
            if turn_count % config.compact_interval_turns == 0:
                compact_round += 1
                messages = compact_messages(
                    messages, config, hook_context, compact_round,
                )

            elif turn_count % config.reactive_interval_turns == 0:
                estimated = estimate_tokens(
                    messages, config.token_estimation_chars_per_token,
                )
                if estimated > config.reactive_trigger_tokens:
                    compact_round += 1
                    messages = reactive_compact(
                        messages, config, hook_context, compact_round,
                    )

            last_compacted_turn = turn_count

        # Load relevant memories for this turn
        load_memories(messages)

        try:
            response, messages, compact_round = safe_api_call(
                client,
                model=model,
                system=get_system_prompt(),
                messages=messages,
                tools=TOOL,
                max_tokens=4096,
                thinking=_build_thinking(),
                extra_body=_build_extra_body(),
                config=config,
                hook_context=hook_context,
                compact_round=compact_round,
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
            # Collect teammate messages before returning
            for tm_msg in teammate.collect_teammate_messages():
                messages.append(tm_msg)

            # Extract and consolidate memories from this session
            extracted = extract_memories(messages)
            if extracted:
                result = consolidate_memories(extracted)
                print(f"[Memory] {result}")
            return messages

        if response.stop_reason == "max_tokens":
            turn_count += 1
            # Append whatever text was generated so far and let the loop continue
            for content_block in response.content:
                if content_block.type == "text":
                    messages.append({"role": "assistant", "content": content_block.text})
            continue

        processed = False
        for content_block in response.content:
            if content_block.type == "text":
                processed = True
                messages.append({"role": "assistant", "content": content_block.text})
            elif content_block.type == "tool_use":
                processed = True
                tool_name = content_block.name
                tool_args = content_block.input

                run_hooks("pretooluse", {
                    "tool_name": tool_name,
                    "arguments": tool_args,
                    "hook_context": hook_context,
                })

                handler = TOOL_HANDLERS.get(tool_name)
                try:
                    if handler and background.should_run_background(tool_name, tool_args):
                        result = background.start_background_task(
                            tool_name, tool_args, handler,
                        )
                    else:
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

        if not processed:
            messages.append({"role": "user", "content": f"[System: unexpected stop_reason={response.stop_reason}]"})


def main():
    scheduler.set_agent_loop(agent_loop)
    scheduler.set_busy(True)
    try:
        messages = []
        agent_loop(messages)
    finally:
        scheduler.set_busy(False)
