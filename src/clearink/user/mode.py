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
        "You are in **Mode 1: Formula / Concept Analysis**.\n\n"
        "Decompose the formula or concept into atomic components, identify prerequisite "
        "knowledge, and recommend verified prerequisite papers with exact "
        "section, paragraph, or equation references."
    ),
    MODE_2: (
        "You are in **Mode 2: Describe Your Confusion**.\n\n"
        "The user describes something they don't understand. Pre-process their description "
        "to identify the core concept and knowledge gap, then build a prerequisite topology "
        "and recommend papers with exact section annotations."
    ),
}

_current_mode = DEFAULT_MODE
_step_mode: bool = False

# Regex to detect /mode N commands, case-insensitive, optional trailing text
_MODE_RE = re.compile(r"^(?:/mode\s*)?([12])\s*$", re.IGNORECASE)


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
        prompt = prompt or _DEFAULT_MODE_PROMPTS.get(target_mode, "")
    except OSError:
        prompt = _DEFAULT_MODE_PROMPTS.get(target_mode, "")

    # Inject LLM output language directive (zh only)
    from .i18n import get_lang_instruction
    lang_inst = get_lang_instruction()
    if lang_inst and prompt:
        prompt = prompt + "\n\n" + lang_inst

    return prompt


def get_mode_label() -> str:
    """Human-readable short label for the current mode (status line)."""
    from .i18n import t
    labels = {
        MODE_1: t("mode1_label_short"),
        MODE_2: t("mode2_label_short"),
    }
    return labels.get(_current_mode, "Unknown")


def get_switch_hint() -> str:
    """Hint text showing how to switch to the other mode."""
    if _current_mode == MODE_1:
        return "/mode 2 to switch"
    return "/mode 1 to switch"


def get_second_input_prompt() -> str:
    """The prompt label for the second input field, mode-dependent."""
    from .i18n import t
    if _current_mode == MODE_1:
        return t("formula_number")
    return t("mode2_second_prompt")


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
            "\nThe user is struggling with a concept they don't understand. "
            "First, pre-process their description: identify the core concept, "
            "determine the knowledge gap, and map it to academic context. "
            "Then build a prerequisite topology (Level 1 → Level 2 → Level 3) "
            "and recommend papers with exact section/paragraph/equation annotations."
        )

    return mode_prefix + "\n".join(parts)


def build_query(paper: str, second_input: str) -> str:
    """Build a user query string for the current mode.

    The mode instructions are prepended so the agent knows which
    behaviour to follow, regardless of the system prompt.
    """
    return build_query_for_mode(paper, second_input, _current_mode)


# ── Step mode ──────────────────────────────────────────────────
# Step mode is implemented as a hard-coded state machine.
# The code controls step numbering and per-step instructions;
# the LLM does NOT decide what step it's on.


def set_step_mode(on: bool) -> None:
    global _step_mode
    _step_mode = on
    if on:
        reset_step_state()


def is_step_mode() -> bool:
    return _step_mode


# ── Step state machine (hard-coded, zero LLM involvement) ─────

_step_number: int = 0           # 0=unstarted, 1=overview, 2=paper list, 3..N+2=per-paper, N+3=summary
_paper_tasks: list[dict] = []   # paper tasks captured after Step 2 (subject, id, etc.)


def reset_step_state() -> None:
    """Reset step counter and paper list (called on /end or new round)."""
    global _step_number, _paper_tasks
    _step_number = 0
    _paper_tasks = []


def advance_step() -> int:
    """Advance to the next step. Returns the new step number."""
    global _step_number
    _step_number += 1
    return _step_number


def get_current_step() -> int:
    """Return the current step number (0 = not started)."""
    return _step_number


def capture_paper_tasks() -> int:
    """Read [READING] tasks from the task system after Step 2 completes.
    Returns the number of papers captured.
    """
    global _paper_tasks
    _paper_tasks = capture_reading_tasks()
    return len(_paper_tasks)


def capture_reading_tasks() -> list[dict]:
    """Return current task-system reading tasks without mutating step globals."""
    try:
        from clearink.tool.task_system.manager import _manager
        return [
            t for t in _manager.get_all()
            if t.get("subject", "").startswith("[READING]")
        ]
    except Exception:
        return []


def get_paper_count() -> int:
    """Return the number of papers in the captured reading list."""
    return len(_paper_tasks)


def build_step_instruction_for(step_number: int, paper_tasks: list[dict] | None = None) -> str:
    """Return the hard-coded instruction for a specific step state.

    This pure helper lets API sessions keep independent step counters while
    the CLI can continue using the module-level state machine.
    """
    paper_tasks = paper_tasks or []
    from .i18n import t

    n = step_number
    total = len(paper_tasks)
    lang_prefix = _get_lang_prefix()

    if n == 1:
        return get_step1_instruction()

    if n == 2:
        return lang_prefix + (
            f"**{t('step2_title')}**\n\n"
            f"{t('step2_body')}\n\n"
            f"{t('nav_next_or_end')}"
        )

    if total > 0 and 3 <= n <= total + 2:
        i = n - 2
        paper = paper_tasks[i - 1]
        paper_title = paper.get("subject", f"Paper {i}").replace("[READING] ", "")
        return lang_prefix + (
            f"**Step {n} — {t('paper')} {i}/{total}: {paper_title}**\n\n"
            f"{t('stepN_instruction')}\n\n"
            f"{t('nav_next_or_end_step')}"
        )

    if (total > 0 and n == total + 3) or (total == 0 and n == 3):
        return lang_prefix + (
            f"**{t('summary_title')}**\n\n"
            f"{t('summary_body').format(total=total)}\n\n"
            f"{t('nav_end_new_round')}"
        )

    return lang_prefix + (
        f"**Step {n}**\n\n"
        f"{t('step_fallback')}\n\n"
        f"{t('nav_next_or_end')}"
    )


def get_step_instruction() -> str:
    """Return the hard-coded instruction for the CURRENT CLI step.

    This is called by _run_step_loop() after advance_step().
    The LLM receives EXACTLY one step's instruction — not all steps.
    """
    return build_step_instruction_for(_step_number, _paper_tasks)


def build_step_instructions() -> str:
    """Return step instructions for the current or first step.

    Used by the API layer (endpoints.py) where there is no CLI step loop.
    Returns Step 1 instructions if step hasn't started, otherwise the
    current step's instruction.
    """
    if _step_number == 0:
        # API layer: treat as starting Step 1
        return get_step1_instruction()
    return get_step_instruction()


def _get_lang_prefix() -> str:
    """Return zh language directive as a prefix, or empty string for en."""
    from .i18n import get_lang_instruction
    lang_inst = get_lang_instruction()
    return lang_inst + "\n\n" if lang_inst else ""


def get_step1_instruction() -> str:
    """Return the Step 1 instruction regardless of current state."""
    from .i18n import t
    return _get_lang_prefix() + (
        f"**{t('step1_title')}**\n\n"
        f"{t('step1_body')}\n\n"
        f"{t('nav_next_or_end')}"
    )
