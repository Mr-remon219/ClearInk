from __future__ import annotations
from typing import Any, Callable

HOOKS: dict[str, list[dict]] = {
    "userpromptsubmit": [],
    "pretooluse": [],
    "posttooluse": [],
    "stop": [],
}

hook_context: dict[str, Any] = {
    "current_paper": None,
    "papers_accessed": [],
    "citation_requested": False,
    "session_log": [],
}

_VALID_TYPES = frozenset(HOOKS.keys())


def register_hook(
    hook_type: str,
    *,
    name: str | None = None,
    priority: int = 100,
) -> Callable[[Callable], Callable]:
    if hook_type not in _VALID_TYPES:
        raise ValueError(
            f"Unknown hook type: {hook_type!r}. Valid types: {sorted(_VALID_TYPES)}"
        )

    def wrapper(fn: Callable) -> Callable:
        hook_name = name or fn.__name__
        HOOKS[hook_type].append({"name": hook_name, "fn": fn, "priority": priority})
        HOOKS[hook_type].sort(key=lambda h: h["priority"])
        return fn

    return wrapper


def run_hooks(hook_type: str, context: dict) -> dict:
    for entry in HOOKS.get(hook_type, []):
        try:
            entry["fn"](context)
        except Exception as exc:
            context.setdefault("hook_errors", []).append(
                {"hook": entry["name"], "type": hook_type, "error": repr(exc)}
            )
    return context
