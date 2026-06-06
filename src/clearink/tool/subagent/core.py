import os
from anthropic import Anthropic
from dotenv import load_dotenv

from ..register import register_tool, TOOL as ALL_TOOLS, TOOL_HANDLERS
from .._llm_loop import run_llm_tool_loop
from ...config import ENV_PATH

load_dotenv(ENV_PATH, override=True)


def _subagent_tools() -> list[dict]:
    return [t for t in ALL_TOOLS if t["name"] != "spawn_subagent"]


@register_tool(
    name="spawn_subagent",
    description="Delegate a task to a sub-agent (flash model, non-thinking). "
                "Suitable for simple parallel work like search, file reads. "
                "Sub-agents cannot recursively call spawn_subagent.",
    input_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Task description for the sub-agent",
            },
        },
        "required": ["prompt"],
    },
)
def spawn_subagent(prompt: str) -> str:
    sub_client = Anthropic()
    messages: list[dict] = [{"role": "user", "content": prompt}]
    tools = _subagent_tools()
    handlers = {k: v for k, v in TOOL_HANDLERS.items() if k != "spawn_subagent"}

    try:
        return run_llm_tool_loop(
            client=sub_client,
            model=os.getenv("SUBAGENT_MODEL", "deepseek-v4-flash"),
            system="You are a focused sub-agent. Complete the assigned task and return results.",
            messages=messages,
            tools=tools,
            handlers=handlers,
            max_turns=5,
        )
    except Exception as e:
        return f"[subagent error: {e}]"
