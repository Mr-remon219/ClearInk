"""Lightweight i18n module — no gettext dependency.

Language is controlled by the CLEARINK_LANG environment variable
(set during the setup wizard or manually in .env).
"""

_lang: str = "en"


def set_lang(lang: str) -> None:
    """Set the current language. ``"zh"`` for Chinese, ``"en"`` for English."""
    global _lang
    normalized = (lang or "").strip().lower()
    _lang = normalized if normalized in ("zh", "en") else "en"


def get_lang() -> str:
    """Return the current language code."""
    return _lang


def get_lang_instruction() -> str:
    """Return a directive telling the LLM to output in the current language.

    Empty for English (the LLM defaults to English).
    Explicit directive for Chinese to prevent mixed-language output.
    """
    if _lang == "zh":
        return "【重要：你必须用中文输出所有内容，包括论文推荐、摘要、分析、解释。禁止使用英文。】"
    return ""


def t(key: str) -> str:
    """Return the translated string for *key* in the current language.

    Falls back to the English string, then to the key itself.
    """
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(_lang, entry.get("en", key))


# ── String table ─────────────────────────────────────────────

_STRINGS: dict[str, dict[str, str]] = {
    # ── Lemon / Welcome ────────────────────────────
    "lemon_subtitle": {
        "en": "Literature Pathfinding Agent",
        "zh": "文献路径导航助手",
    },
    "lemon_name": {
        "en": "ClearInk",
        "zh": "清 砚 / ClearInk",
    },

    # ── Setup wizard ───────────────────────────────
    "setup_title": {
        "en": "ClearInk — First-time Setup",
        "zh": "ClearInk — 首次设置",
    },
    "setup_welcome": {
        "en": "Welcome! No configuration file was found.\nLet's set things up — it only takes a moment.",
        "zh": "欢迎！检测到没有配置文件。\n下面进行首次设置，只需一分钟。",
    },
    "setup_api_key_prompt": {
        "en": "Enter your API key",
        "zh": "请输入您的 API key",
    },
    "setup_api_key_empty": {
        "en": "API key cannot be empty. Please try again.",
        "zh": "API key 不能为空，请重新输入。",
    },
    "setup_lang_prompt": {
        "en": "Use Chinese output? [y/N]",
        "zh": "是否使用中文输出？[y/N]",
    },
    "setup_done": {
        "en": "Setup complete! Configuration saved to data/environment/.env",
        "zh": "设置完成！配置已保存到 data/environment/.env",
    },
    "setup_provider_note": {
        "en": "API provider: DeepSeek (https://api.deepseek.com/anthropic)",
        "zh": "API 服务商：DeepSeek (https://api.deepseek.com/anthropic)",
    },

    # ── Mode selection ─────────────────────────────
    "select_mode": {
        "en": "Select mode:",
        "zh": "选择模式：",
    },
    "mode1_label": {
        "en": "Formula / Concept Analysis",
        "zh": "公式/概念分析",
    },
    "mode1_label_short": {
        "en": "Formula / Concept",
        "zh": "公式/概念",
    },
    "mode2_label": {
        "en": "Describe Your Confusion",
        "zh": "有不会的请描述给我",
    },
    "mode2_label_short": {
        "en": "Describe Confusion",
        "zh": "描述不会的",
    },
    "mode2_second_prompt": {
        "en": "What concept are you struggling with?",
        "zh": "你在哪里卡住了？请描述不理解的概念",
    },
    "mode_prompt": {
        "en": "Mode [1/2]",
        "zh": "模式 [1/2]",
    },
    "mode_switched": {
        "en": "Switched to",
        "zh": "已切换到",
    },

    # ── Input prompts ──────────────────────────────
    "paper_title": {
        "en": "Paper title",
        "zh": "论文标题",
    },
    "formula_number": {
        "en": "Formula number or description",
        "zh": "公式编号或描述",
    },
    "your_question": {
        "en": "Your question about the paper",
        "zh": "您对这篇论文的问题",
    },
    "step_prompt": {
        "en": "Press Enter to start, or type /step for step-by-step output",
        "zh": "按回车开始，或输入 /step 启用分步输出",
    },
    "step_enabled": {
        "en": "Step mode enabled.",
        "zh": "分步输出已启用。",
    },
    "no_title": {
        "en": "No paper title provided.",
        "zh": "未输入论文标题。",
    },
    "analyzing": {
        "en": "Analyzing...",
        "zh": "分析中...",
    },
    "no_response": {
        "en": "(No response received.)",
        "zh": "（未收到回复）",
    },

    # ── Follow-up loop ─────────────────────────────
    "followup_hint": {
        "en": "Ask a follow-up, /step, /mode 1, /mode 2, or /exit to quit.",
        "zh": "输入追问、/step、/mode 1、/mode 2，或 /exit 退出。",
    },
    "round_end": {
        "en": "Round ended. Starting new analysis...",
        "zh": "本轮结束。开始新一轮分析...",
    },
    "step_mode_hint": {
        "en": "Step mode enabled. /next to continue, /end for a new round.",
        "zh": "分步模式已启用。/next 继续，/end 开启新一轮。",
    },
    "session_ended": {
        "en": "Session ended.",
        "zh": "会话已结束。",
    },

    # ── Step loop ──────────────────────────────────
    "step_thinking": {
        "en": "thinking...",
        "zh": "思考中...",
    },
    "already_step": {
        "en": "Already in step mode.",
        "zh": "已在分步模式中。",
    },
    "no_reading_tasks": {
        "en": "No [READING] tasks found. Continuing without paper list tracking.",
        "zh": "未找到 [READING] 任务，继续执行（无论文列表跟踪）。",
    },

    # ── Step 1 — Overview ──────────────────────────
    "step1_title": {
        "en": "Step 1 — Overview",
        "zh": "Step 1 — 总体解释",
    },
    "step1_body": {
        "en": (
            "Give a brief overview of the question, explaining the core conclusion "
            "and reasoning framework. Don't go into details — just clarify "
            "\"what problem are we solving, and what direction is the answer.\"\n\n"
            "Length: 3-5 sentences."
        ),
        "zh": (
            "对用户的问题进行概述，简要说明核心结论和分析框架。"
            "不要深入细节，只交代清楚「要解决什么问题、答案是什么方向」。\n\n"
            "篇幅：3-5 句。"
        ),
    },

    # ── Step 2 — Paper roadmap ─────────────────────
    "step2_title": {
        "en": "Step 2 — Recommended Reading",
        "zh": "Step 2 — 论文路线推荐",
    },
    "step2_body": {
        "en": (
            "List all recommended papers organized by dependency level:\n"
            "- **Level 1**: Papers directly cited by the formula (read first)\n"
            "- **Level 2**: Prerequisite papers needed to understand Level 1\n"
            "- **Level 3**: Foundational textbooks or surveys (read last)\n\n"
            "Each paper must include: title, authors, year. "
            "All metadata must be verified via scholar search --bibtex. Do not fabricate.\n\n"
            "**IMPORTANT: After listing, call create_task for each paper. "
            "Subject MUST start with `[READING]`**, e.g.:\n"
            "`create_task(subject=\"[READING] Attention Is All You Need\")`"
        ),
        "zh": (
            "列出所有推荐阅读的论文，按依赖层级组织：\n"
            "- **Level 1**：公式直接引用的论文（最先读）\n"
            "- **Level 2**：理解 Level 1 所需的前置论文\n"
            "- **Level 3**：基础教材或综述（最后读）\n\n"
            "每篇论文必须包含：标题、作者、年份。"
            "所有元数据必须用 scholar search --bibtex 验证，不得编造。\n\n"
            "**重要：输出完列表后，为每篇论文调用 create_task，"
            "subject 必须以 `[READING]` 开头**，例如：\n"
            "`create_task(subject=\"[READING] Attention Is All You Need\")`"
        ),
    },

    # ── Generic labels ─────────────────────────────
    "paper": {
        "en": "Paper",
        "zh": "第",
    },

    # ── Step 3+ — Per-paper ────────────────────────
    "stepN_instruction": {
        "en": (
            "Output for this paper ONLY:\n"
            "1. **Summary**: 2-3 sentences\n"
            "2. **Recommended reading**: specific chapters/sections/equations\n"
            "3. **Why read this**: explain relevance to the user's question\n\n"
            "Verification: all citations must come from scholar search or teammate results. "
            "If a teammate executed this paper, use inspect_teammate before citing.\n\n"
            "Scope: only this paper — do NOT mention others from the list."
        ),
        "zh": (
            "请只针对这一篇论文输出：\n"
            "1. **论文摘要**：2-3 句概括\n"
            "2. **推荐阅读的具体内容**：列出具体章节/段落/公式编号\n"
            "3. **为什么需要读**：每个推荐段落解释其与用户问题的关联\n\n"
            "验证要求：引用信息必须来自 scholar search 或 teammate 结果，不得编造。"
            "如果该论文有 teammate 执行结果，用 inspect_teammate 检查后再引用。\n\n"
            "篇幅：只讨论这一篇论文，不涉及列表中其他论文。"
        ),
    },

    # ── Final step — Summary ───────────────────────
    "summary_title": {
        "en": "Summary",
        "zh": "总结",
    },
    "summary_body": {
        "en": (
            "Review the reading path for the {total} recommended papers, "
            "summarize the dependency relationships. "
            "Remind the user: send /end to start a new analysis "
            "(re-select mode, paper, formula, step preference)."
        ),
        "zh": (
            "回顾本轮推荐的 {total} 篇论文的阅读路线，总结依赖关系。"
            "提醒用户：发送 /end 可开启新一轮分析"
            "（重新选择 mode、论文、公式、step）。"
        ),
    },

    # ── Navigation markers ─────────────────────────
    "nav_next_or_end": {
        "en": "[Send /next to continue, or /end to end this round]",
        "zh": "[发送 /next 继续下一步，或 /end 结束本轮]",
    },
    "nav_end_new_round": {
        "en": "[Send /end to start a new round]",
        "zh": "[发送 /end 开启新一轮提问]",
    },
    "nav_next_or_end_step": {
        "en": "[Send /next for next paper, or /end to end this round]",
        "zh": "[发送 /next 继续下一篇，或 /end 结束本轮]",
    },

    # ── Fallback ───────────────────────────────────
    "step_fallback": {
        "en": "Please continue based on context.",
        "zh": "请根据上下文继续输出。",
    },
}
