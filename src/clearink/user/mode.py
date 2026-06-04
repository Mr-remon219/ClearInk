"""Mode state management for ClearInk.

Two modes are supported:
    Mode 1 (default) — Formula Dependency Analysis
    Mode 2          — Paper Content Q&A

Mode instructions are injected as a prefix in the user message rather than
modifying the system prompt, avoiding changes to agent_loop and caching.
"""

from pathlib import Path
import re

MODE_1 = 1
MODE_2 = 2
DEFAULT_MODE = MODE_1

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "data" / "system_prompts"

_current_mode = DEFAULT_MODE

# Regex to detect /mode N commands, case-insensitive, optional trailing text
_MODE_RE = re.compile(r"^/mode\s*([12])\s*$", re.IGNORECASE)


def get_mode() -> int:
    return _current_mode


def set_mode(n: int) -> None:
    global _current_mode
    if n not in (MODE_1, MODE_2):
        raise ValueError(f"Invalid mode: {n}. Use 1 or 2.")
    _current_mode = n


def detect_mode_command(text: str) -> int | None:
    """If *text* is a `/mode N` command, return the mode number (1 or 2).
    Returns None otherwise — the text is a normal message.
    """
    m = _MODE_RE.match(text.strip())
    if m:
        return int(m.group(1))
    return None


def get_mode_prompt() -> str:
    """Read the mode instruction file for the current mode."""
    path = _PROMPTS_DIR / f"mode{_current_mode}.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def get_mode_label() -> str:
    """Human-readable label for the current mode."""
    labels = {
        MODE_1: "Formula Analysis",
        MODE_2: "Paper Q&A",
    }
    return labels.get(_current_mode, "Unknown")


def get_switch_hint() -> str:
    """Hint text showing how to switch to the other mode."""
    if _current_mode == MODE_1:
        return "/mode 2 to switch"
    return "/mode 1 to switch"


def get_second_input_prompt() -> str:
    """The prompt label for the second input field, mode-dependent."""
    if _current_mode == MODE_1:
        return "Formula number or description"
    return "Your question about the paper"


def build_query(paper: str, second_input: str) -> str:
    """Build a user query string for the current mode.

    The mode instructions are prepended so the agent knows which
    behaviour to follow, regardless of the system prompt.
    """
    mode_prompt = get_mode_prompt()
    mode_prefix = (
        f"[Mode {_current_mode} instructions begin]\n"
        f"{mode_prompt}\n"
        f"[Mode {_current_mode} instructions end]\n\n"
    ) if mode_prompt else ""

    parts = [f"Paper: {paper}"]
    if second_input:
        if _current_mode == MODE_1:
            parts.append(f"Formula: {second_input}")
        else:
            parts.append(f"Question: {second_input}")

    if _current_mode == MODE_1:
        parts.append(
            "\nPlease analyze the formula above and recommend the prerequisite "
            "papers I need to read to fully understand it. "
            "For each recommended paper, specify the exact section, paragraph, "
            "or equation range that is relevant."
        )
    else:
        parts.append(
            "\nPlease answer the question above about this paper, "
            "then recommend prerequisite papers for deeper understanding. "
            "For each recommended paper, specify the exact section, paragraph, "
            "or equation range that is relevant."
        )

    return mode_prefix + "\n".join(parts)
