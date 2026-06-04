from __future__ import annotations
import json
import os
import threading
import time
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from .register import register_tool, TOOL, TOOL_HANDLERS
from ..config import ENV_PATH
from ..message import content_block_to_dict

load_dotenv(ENV_PATH, override=True)

_SUB_MODEL = os.getenv("SUBAGENT_MODEL", "deepseek-v4-flash")
_EXCLUDED_TOOLS = {"spawn_teammate", "schedule_cron", "cancel_scheduled_job"}

_active_teammates: dict[str, threading.Event] = {}  # name → stop_event
_active_lock = threading.RLock()


# ── Message bus ───────────────────────────────────────────

class MessageBus:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or (
            Path(__file__).resolve().parents[3] / "data" / "team"
        )
        self._lock = threading.RLock()

    def inbox_path(self, name: str) -> Path:
        return self.base_dir / f"{name}_inbox.jsonl"

    def write(self, name: str, message: dict) -> None:
        with self._lock:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            msg = dict(message)
            msg["timestamp"] = time.time()
            with open(self.inbox_path(name), "a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def read_and_clear(self, name: str) -> list[dict]:
        with self._lock:
            path = self.inbox_path(name)
            if not path.exists():
                return []
            try:
                lines = path.read_text(encoding="utf-8").strip().splitlines()
            except OSError:
                return []
            messages = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            path.write_text("", encoding="utf-8")
            return messages

    def collect_for_lead(self) -> list[dict]:
        msgs = self.read_and_clear("lead")
        result = []
        for msg in msgs:
            sender = msg.get("from", "unknown")
            content = msg.get("content", "")
            result.append({
                "role": "user",
                "content": f"[Teammate {sender}]: {content}",
            })
        return result


_bus = MessageBus()


# ── Teammate agent loop ───────────────────────────────────

def _get_teammate_tools() -> tuple[list[dict], dict]:
    tools = [t for t in TOOL if t["name"] not in _EXCLUDED_TOOLS]
    handlers = {
        k: v for k, v in TOOL_HANDLERS.items()
        if k not in _EXCLUDED_TOOLS
    }
    return tools, handlers


def _run_teammate_turn(
    name: str,
    role: str,
    messages: list[dict],
    max_turns: int = 5,
) -> str:
    client = Anthropic()
    tools, handlers = _get_teammate_tools()
    collected: list[str] = []

    for _ in range(max_turns):
        try:
            response = client.messages.create(
                model=_SUB_MODEL,
                system=f"You are {name}, a specialized AI teammate. "
                       f"Role: {role}. "
                       f"Work on the assigned task and report back when done. "
                       f"Be concise and focused.",
                messages=messages,
                tools=tools,
                max_tokens=2048,
                thinking={"type": "disabled"},
            )
        except Exception as e:
            return f"[Teammate {name} error: {e}]"

        if response.stop_reason == "end_turn":
            text = "".join(
                b.text for b in response.content if b.type == "text"
            )
            collected.append(text)
            return "\n".join(filter(None, collected)) or f"[Teammate {name}: no output]"

        for block in response.content:
            if block.type == "text":
                text = block.text or ""
                collected.append(text)
                messages.append({"role": "assistant", "content": text})
            elif block.type == "tool_use":
                handler = handlers.get(block.name)
                try:
                    result = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    result = f"Error: {e}"
                messages.append({"role": "assistant", "content": [content_block_to_dict(block)]})
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    }],
                })

    return "\n".join(filter(None, collected)) + "\n\n[teammate: max turns reached]" if collected else f"[Teammate {name}: max turns reached]"


# ── Idle loop ─────────────────────────────────────────────

def _teammate_idle_loop(name: str, role: str, prompt: str) -> None:
    with _active_lock:
        stop_event = _active_teammates.get(name)
    if stop_event is None:
        return

    # Write initial task as first inbox message
    _bus.write(name, {"role": "user", "content": prompt})

    while not stop_event.is_set():
        msgs = _bus.read_and_clear(name)
        if msgs:
            result = _run_teammate_turn(name, role, msgs)
            _bus.write("lead", {
                "role": "assistant",
                "content": result,
                "from": name,
            })
        time.sleep(2)


# ── Tools ─────────────────────────────────────────────────

@register_tool(
    name="spawn_teammate",
    description="Spawn a teammate agent that runs in the background. "
                "The teammate has its own idle loop and can use tools (reduced set). "
                "Communicate with it via send_to_teammate.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Unique name for the teammate (e.g. 'analyst', 'searcher')",
            },
            "role": {
                "type": "string",
                "description": "Short role description (e.g. 'paper analyst', 'web searcher')",
            },
            "prompt": {
                "type": "string",
                "description": "Initial task for the teammate to work on",
            },
        },
        "required": ["name", "role", "prompt"],
    },
)
def spawn_teammate_thread(name: str, role: str, prompt: str) -> str:
    with _active_lock:
        if name in _active_teammates:
            return f"Error: teammate '{name}' already exists. Names must be unique."
        stop_event = threading.Event()
        _active_teammates[name] = stop_event

    thread = threading.Thread(
        target=_teammate_idle_loop,
        args=(name, role, prompt),
        daemon=True,
    )
    thread.start()

    return (
        f"Teammate '{name}' ({role}) spawned and working on task.\n"
        f"Use send_to_teammate(name='{name}', message=...) to communicate. "
        f"The teammate will report results to your inbox automatically."
    )


@register_tool(
    name="send_to_teammate",
    description="Send a message/task to a teammate. "
                "The teammate will process it and report back to your inbox.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Teammate name to send the message to",
            },
            "message": {
                "type": "string",
                "description": "The message or task for the teammate",
            },
        },
        "required": ["name", "message"],
    },
)
def send_to_teammate(name: str, message: str) -> str:
    with _active_lock:
        active_names = list(_active_teammates)
        if name not in _active_teammates:
            return f"Error: no teammate named '{name}'. Active teammates: {active_names}"

    _bus.write(name, {"role": "user", "content": message})
    return f"Message sent to teammate '{name}'."


@register_tool(
    name="list_teammates",
    description="List all active teammates.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def list_teammates() -> str:
    with _active_lock:
        active_names = list(_active_teammates)
    if not active_names:
        return "(no active teammates)"
    return "Active teammates:\n" + "\n".join(
        f"  - {name}" for name in active_names
    )


@register_tool(
    name="stop_teammate",
    description="Stop and remove a teammate by name.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Teammate name to stop"},
        },
        "required": ["name"],
    },
)
def stop_teammate(name: str) -> str:
    with _active_lock:
        stop_event = _active_teammates.pop(name, None)
    if stop_event is None:
        return f"Error: no teammate named '{name}'."
    stop_event.set()
    return f"Teammate '{name}' stopped."


# ── Lead inbox collection ─────────────────────────────────

def collect_teammate_messages() -> list[dict]:
    return _bus.collect_for_lead()
