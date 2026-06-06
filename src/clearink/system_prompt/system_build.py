"""System prompt assembly — reads prompt sections from data/system_prompts/.

The section registry pattern is preserved for extensibility, even though
currently only "guidelines" is registered.  New sections (e.g. tool-specific
instructions) can be added by registering a builder in PROMPT_SECTIONS.
"""

from __future__ import annotations
from typing import Callable

from ..config import SYSTEM_PROMPTS_DIR

_PROMPTS_DIR = SYSTEM_PROMPTS_DIR


# ── Helpers ─────────────────────────────────────────────────

def _read_prompt_file(filename: str) -> str | None:
    path = _PROMPTS_DIR / filename
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, FileNotFoundError):
        return None


# ── Section builders ────────────────────────────────────────

def _build_guidelines(_ctx: dict) -> str:
    return _read_prompt_file("guidelines.md") or (
        "You are ClearInk, a literature-assisted reading agent. "
        "- NEVER fabricate paper metadata; verify via scholar search. "
        "- Present specific section/paragraph annotations for every recommended paper. "
        "- Be precise and concise."
    )


# ── Section registry ────────────────────────────────────────

PROMPT_SECTIONS: dict[str, Callable[[dict], str]] = {
    "guidelines": _build_guidelines,
}


# ── Public API ──────────────────────────────────────────────

def get_system_prompt(sections: list[str] | None = None) -> str:
    """Return the assembled system prompt."""
    keys = sections if sections is not None else list(PROMPT_SECTIONS.keys())
    parts = []
    for key in keys:
        builder = PROMPT_SECTIONS.get(key)
        if builder is not None:
            part = builder({})
            if part:
                parts.append(part)

    # Inject LLM output language directive (zh only; en path unaffected)
    from ..user.i18n import get_lang_instruction
    lang_inst = get_lang_instruction()
    if lang_inst:
        parts.append(lang_inst)

    return "\n\n".join(parts)
