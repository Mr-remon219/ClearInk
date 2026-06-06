from anthropic import Anthropic
from dotenv import load_dotenv
from datetime import datetime
import os

from .config import ENV_PATH
from .tool.register import TOOL, TOOL_HANDLERS
from .tool import basetool, subagent, task_system, team, mcp_client, regulation  # noqa: F401 — registers tools
from .tool.mcp_client import assemble_tool_pool
from .hook import run_hooks, hook_context
from .system_prompt.system_build import get_system_prompt
from .error_recovery.wrapper import safe_api_call
from .context_compact import CompactConfig, compact_messages, reactive_compact
from .context_compact.token_estimate import estimate_tokens
from .message import content_blocks_to_dicts

load_dotenv(ENV_PATH, override=True)
_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _get_model() -> str | None:
    model = os.getenv("MODEL")
    return model.strip() if model else None


def _thinking_budget() -> int:
    raw = os.getenv("THINKING_BUDGET", "0") or "0"
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _build_thinking() -> dict | None:
    thinking_type = (os.getenv("THINKING_TYPE") or "").strip().lower()
    if thinking_type not in {"enabled", "disabled"}:
        return None
    t = {"type": thinking_type}
    thinking_budget = _thinking_budget()
    if thinking_type == "enabled" and thinking_budget > 0:
        t["budget_tokens"] = thinking_budget
    return t


def _build_extra_body() -> dict:
    body = {}
    effort = os.getenv("THINKING_EFFORT")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "")
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
        current_model = _get_model()
        if not current_model:
            messages.append({
                "role": "assistant",
                "content": "[Configuration error] MODEL is not set in data/environment/.env.",
            })
            return messages

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

        try:
            # Merge MCP-discovered tools into the tool pool
            mcp_tools, mcp_handlers = assemble_tool_pool()
            all_tools = TOOL + mcp_tools

            response, messages, compact_round = safe_api_call(
                _get_client(),
                model=current_model,
                system=get_system_prompt(),
                messages=messages,
                tools=all_tools,
                max_tokens=4096,
                thinking=_build_thinking(),
                extra_body=_build_extra_body(),
                config=config,
                hook_context=hook_context,
                compact_round=compact_round,
            )
        except Exception as e:
            messages.append({
                "role": "assistant",
                "content": f"[Error] API call failed after retries: {e}",
            })
            return messages

        assistant_content = content_blocks_to_dicts(response.content)
        messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason == "end_turn":
            turn_count += 1
            run_hooks("stop", {
                "messages": messages,
                "turns": turn_count,
                "hook_context": hook_context,
            })
            # Collect teammate messages before returning
            for tm_msg in team.collect_teammate_messages():
                messages.append(tm_msg)
            return messages

        if response.stop_reason == "max_tokens":
            messages.append({
                "role": "assistant",
                "content": "[Error] Response was still truncated after max token expansion.",
            })
            return messages

        tool_blocks = [
            block for block in assistant_content
            if block.get("type") == "tool_use"
        ]
        if not tool_blocks:
            messages.append({
                "role": "assistant",
                "content": f"[Error] Unexpected stop_reason={response.stop_reason}",
            })
            return messages

        tool_results = []
        for tool_block in tool_blocks:
            tool_name = str(tool_block.get("name", ""))
            raw_tool_args = tool_block.get("input") or {}
            tool_args = raw_tool_args if isinstance(raw_tool_args, dict) else {}

            run_hooks("pretooluse", {
                "tool_name": tool_name,
                "arguments": tool_args,
                "hook_context": hook_context,
            })

            handler = TOOL_HANDLERS.get(tool_name) or mcp_handlers.get(tool_name)
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

            result_content = error if error is not None else result
            if result_content is None:
                result_content = ""
            elif not isinstance(result_content, str):
                result_content = str(result_content)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": str(tool_block.get("id", "")),
                "content": result_content,
            })

        messages.append({"role": "user", "content": tool_results})


def main():
    from clearink.user import run

    run(agent_loop)
