"""Mode state management for ClearInk.

Two modes are supported:
    Mode 1 (default) — Formula Dependency Analysis
    Mode 2          — Paper Content Q&A

Mode instructions are injected as a prefix in the user message rather than
modifying the system prompt, avoiding changes to agent_loop and caching.
"""

import re

from clearink.config import SYSTEM_PROMPTS_DIR
from clearink.hook import run_hooks

MODE_1 = 1
MODE_2 = 2
DEFAULT_MODE = MODE_1

_PROMPTS_DIR = SYSTEM_PROMPTS_DIR

_DEFAULT_MODE_PROMPTS = {
    MODE_1: (
        "You are in **Mode 1: Formula Dependency Analysis**.\n\n"
        "Decompose the formula into atomic components, identify prerequisite "
        "knowledge, and recommend verified prerequisite papers with exact "
        "section, paragraph, or equation references."
    ),
    MODE_2: (
        "You are in **Mode 2: Paper Content Q&A**.\n\n"
        "Answer the user's paper question briefly and directly, then recommend "
        "verified prerequisite or related papers with exact relevant sections."
    ),
}

_current_mode = DEFAULT_MODE
_step_mode: bool = False

# Regex to detect /mode N commands, case-insensitive, optional trailing text
_MODE_RE = re.compile(r"^/mode\s*([12])\s*$", re.IGNORECASE)


def get_mode() -> int:
    return _current_mode


def set_mode(n: int) -> None:
    global _current_mode
    _validate_mode(n)
    old = _current_mode
    if old == n:
        return
    _current_mode = n
    run_hooks("mode_switched", {"old_mode": old, "new_mode": n})


def detect_mode_command(text: str) -> int | None:
    """If *text* is a `/mode N` command, return the mode number (1 or 2).
    Returns None otherwise — the text is a normal message.
    """
    m = _MODE_RE.match(text.strip())
    if m:
        return int(m.group(1))
    return None


def get_mode_prompt(mode: int | None = None) -> str:
    """Read the mode instruction file for *mode* or the current mode."""
    target_mode = _current_mode if mode is None else mode
    path = _PROMPTS_DIR / f"mode{target_mode}.md"
    try:
        prompt = path.read_text(encoding="utf-8").strip()
        return prompt or _DEFAULT_MODE_PROMPTS.get(target_mode, "")
    except OSError:
        return _DEFAULT_MODE_PROMPTS.get(target_mode, "")


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


def _validate_mode(n: int) -> None:
    if n not in (MODE_1, MODE_2):
        raise ValueError(f"Invalid mode: {n}. Use 1 or 2.")


def build_query_for_mode(paper: str, second_input: str, mode: int) -> str:
    """Build a user query string for a specific mode without changing globals.

    Useful for API integrations where concurrent sessions can use different
    modes and should not temporarily mutate the process-wide CLI mode.
    """
    _validate_mode(mode)
    mode_prompt = get_mode_prompt(mode)
    mode_prefix = (
        f"[Mode {mode} instructions begin]\n"
        f"{mode_prompt}\n"
        f"[Mode {mode} instructions end]\n\n"
    ) if mode_prompt else ""

    parts = [f"Paper: {paper}"]
    if second_input:
        if mode == MODE_1:
            parts.append(f"Formula: {second_input}")
        else:
            parts.append(f"Question: {second_input}")

    if mode == MODE_1:
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


def build_query(paper: str, second_input: str) -> str:
    """Build a user query string for the current mode.

    The mode instructions are prepended so the agent knows which
    behaviour to follow, regardless of the system prompt.
    """
    return build_query_for_mode(paper, second_input, _current_mode)


# ── Step mode ──────────────────────────────────────────────────


def set_step_mode(on: bool) -> None:
    global _step_mode
    _step_mode = on
    run_hooks("step_mode_changed", {"step_mode": on})


def is_step_mode() -> bool:
    return _step_mode


def build_step_instructions() -> str:
    """Return instructions injected into the user message in step mode.

    Tells the LLM to output in sequential stages with /next to
    continue and /end to start a new round.
    """
    return (
        "[Step mode active — 分步输出模式]\n"
        "你必须按以下步骤分步输出回答，每步结束后等待用户发送 /next 继续：\n\n"
        "**Step 1 — 总体解释**\n"
        "对问题进行概述，给出核心结论和回答框架。\n\n"
        "**Step 2 — 论文路线推荐**\n"
        "推荐阅读路线，列出需要阅读的关键论文（含依赖关系），"
        "按直接引用→一级背景→基础文献三级标注。\n\n"
        "**Step 3+ — 逐篇论文详细说明**\n"
        "对每篇推荐论文依次给出：\n"
        "- 论文摘要（2-3句）\n"
        "- 推荐阅读的具体段落/公式编号\n"
        "- 该段落的概括（解释为什么需要读这一段）\n\n"
        "**最后一步 — 总结**\n"
        "总结推荐路线，提示用户发送 /end 开启新一轮提问。\n\n"
        "**重要规则：**\n"
        "- 每一步输出末尾标注: [发送 /next 继续下一步，或 /end 结束本轮]\n"
        "- 在最后一步末尾标注: [发送 /end 开启新一轮提问]\n"
        "- 严格遵循反幻觉规则，不编造论文信息\n"
    )
