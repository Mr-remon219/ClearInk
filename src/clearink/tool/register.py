from typing import Callable, Any

### TOOL用来存放工具信息，示例：TOOL = [{"name": ***, "description": ***, "input_schema": {"type": ***, "properties": {***:***, "required": []}}}],toolhandler用来根据name来路由
TOOL: list[dict] = []    
TOOL_HANDLERS: dict = {}

### 装饰器，自动将函数装载至TOOL中
def register_tool(name: str, description: str, input_schema: dict) -> Callable[..., Any]:
    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        TOOL.append({"name": name, "description": description, "input_schema": input_schema})
        TOOL_HANDLERS[name] = fn
        return fn
    return wrapper


    