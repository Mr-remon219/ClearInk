from __future__ import annotations
from pathlib import Path
from datetime import datetime
import platform
from typing import Callable

from ..tool.skill import get_available_skills
from ..tool.register import TOOL_HANDLERS

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "data" / "system_prompts"
_MEMORY_DIR = _PROMPTS_DIR / ".memory"

# ── Cache ──────────────────────────────────────────────────
_last_key: str = ""
_last_context: dict = {}
_last_prompt: str = ""

# ── Context ────────────────────────────────────────────────
_current_memories: str = ""


def set_current_memories(content: str) -> None:
    global _current_memories
    _current_memories = content


def _build_context() -> dict:
    return {
        "enabled_tools": sorted(TOOL_HANDLERS.keys()),
        "workspace": str(Path.cwd()),
        "memories": _current_memories,
    }


# ── Individual builders ───────────────────────────────────

def _read_file(filename: str) -> str | None:
    path = _PROMPTS_DIR / filename
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, FileNotFoundError):
        return None


def _build_base(context: dict) -> str:
    return _read_file("base.md") or (
        "You are ClearInk, a literature-assisted reading agent. "
        "Your primary function is to help users understand academic papers "
        "by analyzing formulas and recommending prerequisite readings."
    )


def _build_guidelines(context: dict) -> str:
    return _read_file("guidelines.md") or (
        "=== Guidelines ===\n"
        "- NEVER fabricate paper metadata; verify via scholar search.\n"
        "- Present specific section/paragraph annotations for every recommended paper.\n"
        "- Be precise and concise."
    )


def _build_memory_rules(context: dict) -> str:
    path = _MEMORY_DIR / "memory.md"
    try:
        content = path.read_text(encoding="utf-8").strip()
        return content if content else ""
    except (OSError, FileNotFoundError):
        return ""


def _build_memory_index(context: dict) -> str:
    path = _MEMORY_DIR / "MEMORY.md"
    try:
        content = path.read_text(encoding="utf-8").strip()
    except (OSError, FileNotFoundError):
        content = ""
    if not content:
        return "=== Current Memories ===\n(no memories stored yet)"

    memories_text = context.get("memories", "")
    if memories_text:
        return f"=== Current Memories ===\n{content}\n\n{memories_text}"
    return f"=== Current Memories ===\n{content}"


def _build_skills(context: dict) -> str:
    skills = get_available_skills()
    if not skills:
        return ""
    lines = ["=== Available Skills ==="]
    for name, info in skills.items():
        lines.append(f"- {name}: {info['description']}")
    lines.append("")
    lines.append(
        "When a skill matches the user's request, invoke load_skill "
        "to get full instructions before acting."
    )
    return "\n".join(lines)


def _build_environment(context: dict) -> str:
    ws = context.get("workspace", str(Path.cwd()))
    return (
        "=== Environment ===\n"
        f"- Working directory: {ws}\n"
        f"- OS: {platform.system()} {platform.release()}\n"
        f"- Date: {datetime.now().strftime('%Y-%m-%d')}"
    )


# ── Section registry ──────────────────────────────────────

PROMPT_SECTIONS: dict[str, Callable[[dict], str]] = {
    "base":          _build_base,
    "guidelines":    _build_guidelines,
    "memory_rules":  _build_memory_rules,
    "memory_index":  _build_memory_index,
    "skills":        _build_skills,
    "environment":   _build_environment,
}


# ── Public API ────────────────────────────────────────────

def assemble_system_prompt(
    sections: list[str] | None = None,
    context: dict | None = None,
) -> str:
    ctx = context or _build_context()
    keys = sections if sections is not None else list(PROMPT_SECTIONS.keys())
    parts = []
    for key in keys:
        builder = PROMPT_SECTIONS.get(key)
        if builder is None:
            continue
        part = builder(ctx)
        if part:
            parts.append(part)
    return "\n\n".join(parts)


def get_system_prompt(sections: list[str] | None = None) -> str:
    global _last_key, _last_context, _last_prompt

    ctx = _build_context()
    key = (
        tuple(ctx["enabled_tools"]),
        ctx["workspace"],
        ctx["memories"],
        tuple(sections) if sections is not None else None,
    )

    key_str = str(hash(key))
    if key_str == _last_key and _last_prompt:
        return _last_prompt

    _last_key = key_str
    _last_context = ctx
    _last_prompt = assemble_system_prompt(sections, ctx)
    return _last_prompt


# ── Backward compat ───────────────────────────────────────
def system_build() -> str:
    return get_system_prompt()
