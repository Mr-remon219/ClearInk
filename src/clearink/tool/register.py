from typing import Callable, Any

TOOL: list[dict] = []
TOOL_HANDLERS: dict = {}


def register_tool(name: str, description: str, input_schema: dict) -> Callable[..., Any]:
    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in TOOL_HANDLERS:
            raise ValueError(f"Duplicate tool registration: {name}")
        TOOL.append({"name": name, "description": description, "input_schema": input_schema})
        TOOL_HANDLERS[name] = fn
        return fn
    return wrapper
