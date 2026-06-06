"""Shared LLM tool-use loop — used by both teammates and subagents.

Extracted from the nearly-identical loops in team/lifecycle.py and
subagent/core.py.  Single optimization point for both code paths.
"""

from __future__ import annotations

from ..message import content_block_to_dict


def run_llm_tool_loop(
    client,                # Anthropic client instance
    model: str,
    system: str,
    messages: list[dict],
    tools: list[dict],
    handlers: dict,
    max_turns: int = 5,
    max_tokens: int = 2048,
    thinking: dict | None = None,
) -> str:
    """Run up to *max_turns* LLM calls, dispatching tool-use blocks.

    Returns concatenated text output from all turns, or an empty marker
    if no text was produced.  Lets API exceptions propagate to callers
    so they can distinguish transient failures from empty results.
    """
    collected: list[str] = []

    for _ in range(max_turns):
        response = client.messages.create(
            model=model,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            thinking=thinking or {"type": "disabled"},
        )

        if response.stop_reason == "end_turn":
            text = "".join(
                b.text for b in response.content if b.type == "text"
            )
            collected.append(text)
            return "\n".join(filter(None, collected)) or "[no output]"

        # Collect all blocks into a single assistant message (matching
        # how main.py:142 uses content_blocks_to_dicts for proper structure)
        assistant_blocks: list[dict] = []
        tool_results: list[dict] = []

        for block in response.content:
            if block.type == "text":
                collected.append(block.text or "")
                assistant_blocks.append(content_block_to_dict(block))
            elif block.type == "tool_use":
                assistant_blocks.append(content_block_to_dict(block))
                handler = handlers.get(block.name)
                try:
                    result = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    result = f"Error: {e}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

        messages.append({"role": "assistant", "content": assistant_blocks})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    if collected:
        return "\n".join(collected) + "\n\n[max turns reached]"
    return "[max turns reached]"
