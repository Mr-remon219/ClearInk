import os
from anthropic import Anthropic
from .register import register_tool, TOOL as ALL_TOOLS, TOOL_HANDLERS


def _subagent_tools() -> list[dict]:
    return [t for t in ALL_TOOLS if t["name"] != "spawn_subagent"]


@register_tool(
    name="spawn_subagent",
    description="将任务委派给子代理(flash模型,非思考模式)执行，"
                "适合简单并行的搜索、读文件等任务。子代理不能递归调用 spawn_subagent。",
    input_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "子代理要执行的任务描述",
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
    collected_text: list[str] = []

    for _ in range(5):
        response = sub_client.messages.create(
            model=os.getenv("SUBAGENT_MODEL"),
            messages=messages,
            tools=tools,
            max_tokens=2048,
            thinking={"type": "disabled"},
        )

        if response.stop_reason == "end_turn":
            text = "".join(
                b.text for b in response.content if b.type == "text"
            )
            collected_text.append(text)
            return "\n".join(filter(None, collected_text)) or "[subagent returned no text]"

        for block in response.content:
            if block.type == "text":
                text = block.text or ""
                collected_text.append(text)
                messages.append({"role": "assistant", "content": text})
            elif block.type == "tool_use":
                handler = handlers.get(block.name)
                try:
                    result = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    result = f"Error: {e}"
                messages.append({"role": "assistant", "content": [block]})
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    }],
                })

    if collected_text:
        return "\n".join(collected_text) + "\n\n[subagent: max turns reached]"
    return "[subagent: max turns reached]"
