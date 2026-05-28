from __future__ import annotations
from pathlib import Path
from datetime import datetime
import platform

from .tool.skill import get_available_skills

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "system_prompts"


def system_build() -> str:
    parts = [
        _read_file("base.md") or _fallback_base(),
        _read_file("guidelines.md") or _fallback_guidelines(),
        _build_skills_section(),
        _build_env_section(),
    ]
    return "\n\n".join(p for p in parts if p)


def _read_file(filename: str) -> str | None:
    path = _PROMPTS_DIR / filename
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, FileNotFoundError):
        return None


def _fallback_base() -> str:
    return (
        "You are ClearInk, a literature-assisted reading agent. "
        "Your primary function is to help users understand academic papers "
        "by analyzing formulas and recommending prerequisite readings."
    )


def _fallback_guidelines() -> str:
    return (
        "=== Guidelines ===\n"
        "- NEVER fabricate paper metadata; verify via scholar search.\n"
        "- Present specific section/paragraph annotations for every recommended paper.\n"
        "- Be precise and concise."
    )


def _build_skills_section() -> str:
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


def _build_env_section() -> str:
    return (
        "=== Environment ===\n"
        f"- Working directory: {Path.cwd()}\n"
        f"- OS: {platform.system()} {platform.release()}\n"
        f"- Date: {datetime.now().strftime('%Y-%m-%d')}"
    )
