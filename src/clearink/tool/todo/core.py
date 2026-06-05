import threading

from ..register import register_tool

CURRENT_TODOS: list[dict] = []
_TODO_LOCK = threading.RLock()

_STATUS_ICONS = {
    "pending": " ",
    "in_progress": "~",
    "completed": "x",
}


def get_todos() -> list[dict]:
    with _TODO_LOCK:
        return [item.copy() for item in CURRENT_TODOS]


def _format_todos() -> str:
    with _TODO_LOCK:
        if not CURRENT_TODOS:
            return "(no todos)"
        lines = []
        for i, item in enumerate(CURRENT_TODOS, 1):
            icon = _STATUS_ICONS.get(item.get("status", "pending"), " ")
            content = item.get("content", "")
            lines.append(f"[{icon}] #{i}: {content}")
        return "\n".join(lines)


@register_tool(
    name="todo_write",
    description="维护简单的扁平 TODO 列表（无依赖关系）。"
                "如需带前置依赖的任务管理，请使用 create_task/claim_task/complete_task。"
                "merge=true 时按 id 合并(新增或更新)，merge=false 时全量替换。",
    input_schema={
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "任务项列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "任务唯一标识"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "任务状态",
                        },
                        "content": {"type": "string", "description": "任务描述"},
                    },
                    "required": ["id", "content"],
                },
            },
            "merge": {
                "type": "boolean",
                "description": "是否按 id 合并(默认 true)，false 则全量替换",
            },
        },
        "required": ["todos"],
    },
)
def todo_write(todos: list[dict], merge: bool = True) -> str:
    global CURRENT_TODOS

    with _TODO_LOCK:
        if not merge:
            CURRENT_TODOS = [item.copy() for item in todos]
            return _format_todos()

        for item in todos:
            item_id = item.get("id")
            existing = next((t for t in CURRENT_TODOS if t.get("id") == item_id), None)
            if existing:
                existing.update(item)
            else:
                CURRENT_TODOS.append(item.copy())

        return _format_todos()
