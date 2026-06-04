<p align="center">
  <samp>ClearInk</samp>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.14%2B-blue?style=flat-square" alt="Python 3.14+">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/build-uv-f7df1e?style=flat-square" alt="uv build">
  <img src="https://img.shields.io/badge/status-alpha-999?style=flat-square" alt="Alpha">
</p>

<p align="center">
  <sub><a href="README.md">English</a> | <a href="README_zh.md">简体中文</a></sub>
</p>

---

**ClearInk** is a dual-mode academic reading agent. In **Mode 1** (default) you give it a paper title and a formula you do not understand; it decomposes the formula, verifies citation metadata through Google Scholar, and returns a prerequisite reading path with specific section, paragraph, or equation references. In **Mode 2** you ask a question about a paper's content; it gives a brief answer, then recommends prerequisite papers for deeper understanding. Modes are switchable mid-session with `/mode 1` or `/mode 2`.

ClearInk ships with a Rich terminal interface — a lemon pixel-art welcome screen, mode-aware prompts, spinner feedback, and Markdown rendering — styled after the clean CLI aesthetics of modern developer tools.

Under the hood, ClearInk is also a compact Python agent runtime: an Anthropic-compatible CLI loop, decorator-registered tools, `SKILL.md` extensions, persistent memory, hooks, sub-agents, teammate threads, cron scheduling, DAG tasks, context compaction, and error recovery.

The project is currently **alpha**. The citation policy is strict by design: paper metadata must come from `scholar --bibtex` or `scholar cite`; missing fields should be reported as unavailable, not guessed. Section-level annotations are only as strong as the retrieved evidence available to the agent.

---

## Why ClearInk Exists

Reading a research paper is rarely linear. To give a simple example: when a computer science paper uses

```text
D(X+Y) = D(X) + D(Y) + 2Cov(X,Y)
```

the paper may assume that you already know the covariance expansion, the notation conventions, and the proof context. Following that trail manually can turn into hours of citation chasing. General-purpose LLMs often fill the gaps from memory and produce plausible but wrong titles, years, authors, or page references.

ClearInk treats paper reading as a dependency problem:

1. identify the pieces of a formula or concept,
2. search for the prerequisite papers or explanations,
3. rank those sources by dependency depth,
4. present a reading path with verified metadata and explicit uncertainty.

---

## What Is Implemented

ClearInk currently provides:

- **Rich terminal interface** — pixel-art lemon welcome screen, mode-aware input prompts, spinner feedback, and rendered Markdown output via the `rich` library.
- **Dual-mode interaction** — `/mode 1` for formula dependency analysis, `/mode 2` for paper content Q&A. Switchable at any prompt without restarting the session.
- **Interactive CLI workflow** — prompts for a paper title and a mode-dependent second input (formula or question), then supports follow-up questions in the same session.
- **Prompt-assembled academic agent** — builds the system prompt from `data/system_prompts/base.md`, `guidelines.md`, available skills, memories, and runtime environment.
- **Google Scholar skill** — loads `data/skills/google_scholar/SKILL.md` when academic search or citation work is needed, with a hard rule to verify metadata through the `scholar` CLI.
- **22 registered tool schemas** — shell execution, file reading, glob search, skills, memory, todos, DAG tasks, background tasks, sub-agents, teammate threads, and cron jobs.
- **Reading hooks** — detect citation-related prompts, inject citation-verification reminders, track accessed paper-like files, and write a local `data/logs/reading-journal.md`.
- **Persistent memory** — stores project, user, feedback, reference, and knowledge memories as Markdown files with YAML frontmatter.
- **Context compaction** — trims middle exchanges, archives large tool outputs, replaces large message bodies with placeholders, and summarizes long sessions.
- **Error recovery** — retries transient API errors, reacts to context overflow through compaction, and expands `max_tokens` for truncated outputs.

---

## Architecture

```text
                           clearink CLI
                                |
                     Rich terminal interface
                  user/ (console, interface, mode)
                                |
                     Paper title + input prompt
                                |
               System prompt assembly
        base.md + guidelines.md + skills + memories + env
                                |
               +----------------+----------------+
               |                |                |
          Hook system      Memory system     Error recovery
          4 hook points    frontmatter MD    retry/overflow/truncation
               |                |                |
               +----------------+----------------+
                                |
                          Agent loop
                                |
        +-----------+-----------+-----------+-----------+
        |           |           |           |           |
    Tool registry  Skills   Sub-agents   Teammates   Scheduler
    @register      SKILL.md  delegate     JSONL bus   cron
        |
  +-----+-----+-----+-----+-----+-----+
  |     |     |     |     |     |     |
 bash  file  glob  task  todo memory ...
                                |
               Context compaction L1-L4
      trim / placeholder / archive / summarize
```

---

## Academic Workflow & Modes

ClearInk operates in two modes, switchable at any prompt with `/mode 1` or `/mode 2`:

### Mode 1 — Formula Dependency Analysis (default)

- **Formula decomposition** — the agent breaks formulas into symbols, operators, theorem references, and assumed background.
- **Prerequisite ranking** — recommendations are organized by dependency depth: direct dependencies, background papers, and foundational references.
- **Citation verification** — bibliographic metadata must be obtained from Google Scholar BibTeX output before presentation.
- **Evidence-aware annotations** — section, paragraph, and equation references are given only when supported by retrieved evidence.
- **Uncertainty discipline** — missing metadata or unavailable section evidence is stated plainly instead of inferred.

Example Mode 1 prompt:

```text
Mode 1 · Formula Analysis  (/mode 2 to switch)

Paper title: Attention Is All You Need
Formula number or description: scaled dot-product attention, Attention(Q,K,V) = softmax(QK^T / sqrt(d_k))V
```

### Mode 2 — Paper Content Q&A

- **Brief answer first** — the agent gives a concise 2-4 sentence answer to the user's question before listing papers.
- **Prerequisite reading** — then recommends papers that deepen understanding of the topic, with section-level annotations.
- Same citation verification and anti-hallucination rules apply.

Example Mode 2 prompt:

```text
Mode 2 · Paper Q&A  (/mode 1 to switch)

Paper title: BERT: Pre-training of Deep Bidirectional Transformers
Your question about the paper: Why does BERT use layer normalization before the attention sub-layer instead of after?
```

---

## Runtime Features

| Component | Role | Reusable For |
|-----------|------|-------------|
| `@register_tool` | Decorator-based tool registry with JSON Schema-style tool definitions | Extensible agent tooling |
| `SKILL.md` loader | Dynamic skill discovery from `data/skills/*/SKILL.md` frontmatter | Domain-specific behavior without code changes |
| Sub-agent delegation | Flash-model sub-agent with thinking disabled and up to 5 tool turns | Cheap parallel lookup or file-reading tasks |
| Teammate message bus | Background teammate threads communicating through JSONL inboxes | Multi-agent collaboration experiments |
| DAG task system | Dependency-resolved task graph with claim/complete/unblock flow | Research planning and workflow tracking |
| Context compaction | L1-L4 compression for long conversations | Long-running sessions under token limits |
| Error recovery | Retry, context overflow recovery, and truncation retry handling | More resilient API calls |
| Hook system | `userpromptsubmit`, `pretooluse`, `posttooluse`, and `stop` hooks | Logging, policy reminders, and reading context |
| Persistent memory | Markdown + YAML frontmatter memory store | User preferences and project knowledge |
| Cron scheduler | 5-field cron jobs persisted to JSON | Recurring research prompts |

---

## Quick Start

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- An Anthropic-compatible API key and endpoint
- Optional but important for citation verification: the `scholar` CLI on `PATH`

### Install

```bash
git clone https://github.com/Mr-remon219/ClearInk.git
cd ClearInk
uv sync
```

### Configure

Create `data/environment/.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://api.anthropic.com
MODEL=claude-opus-4-1-20250805

# Optional thinking controls
THINKING_TYPE=enabled
THINKING_BUDGET=4096

# Optional DeepSeek-compatible effort field
THINKING_EFFORT=max

# Optional cheaper model for sub-agents and teammates
SUBAGENT_MODEL=deepseek-v4-flash
```

If you use the Google Scholar skill, also make sure `scholar` is installed and authenticated:

```bash
command -v scholar
scholar auth
```

### Run

```bash
uv run clearink
```

The CLI displays a lemon pixel-art welcome screen, shows the current mode, then prompts:

```text
  Mode 1 · Formula Analysis  (/mode 2 to switch)

Paper title: Attention Is All You Need
Formula number or description: scaled dot-product attention formula

  Analyzing...
```

After the first answer, use the follow-up prompt for refinements, switch modes with `/mode 1` or `/mode 2`, or exit with `/exit`.

---

## Project Structure

```text
ClearInk/
├── pyproject.toml
├── README.md
├── README_zh.md
├── LICENSE
├── data/
│   ├── environment/.env        runtime API configuration, not committed
│   ├── skills/
│   │   └── google_scholar/
│   │       └── SKILL.md
│   ├── system_prompts/
│   │   ├── base.md
│   │   ├── guidelines.md
│   │   ├── mode1.md            Mode 1 instructions (formula analysis)
│   │   ├── mode2.md            Mode 2 instructions (paper Q&A)
│   │   └── .memory/            runtime memory files
│   ├── .tasks/                 runtime DAG task persistence
│   ├── .scheduled_tasks/       runtime cron persistence
│   ├── .transcripts/           runtime compaction archives
│   ├── team/                   runtime teammate message bus
│   └── task_outputs/           archived large tool results
└── src/clearink/
    ├── main.py                 entry point and agent loop
    ├── config.py
    ├── context_compact/        L1-L4 compaction
    ├── error_recovery/         retry, overflow, truncation
    ├── hook/                   pluggable hooks and reading hooks
    ├── message/                content block serialization and text extraction
    ├── system_prompt/          prompt assembly and memory
    ├── tool/                   registered tools
    └── user/                   Rich CLI interface
        ├── console.py          console theme and lemon pixel art
        ├── interface.py        interactive prompt loop
        ├── mode.py             mode state and command detection
        └── output_format.py    LaTeX to plain-text conversion
```

Some `data/` subdirectories are created at runtime and may not exist in a fresh clone.

---

## Extending ClearInk

### Add a Tool

```python
from clearink.tool.register import register_tool


@register_tool(
    name="arxiv_search",
    description="Search ArXiv by keyword and return paper metadata",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
        },
        "required": ["query"],
    },
)
def arxiv_search(query: str) -> str:
    return f"Results for: {query}"
```

Import the module from `clearink.tool.__init__` or another imported module so the decorator runs during startup.

### Add a Skill

Create `data/skills/zotero/SKILL.md`:

```markdown
---
name: zotero
description: Query and manage a local Zotero library via the zotero-cli tool
---

# Zotero Skill

Use the `zotero` CLI to search, export, and manage citations...
```

Skills are discovered at runtime and exposed to the agent through `load_skill`.

### Add a Hook

```python
from clearink.hook.hook import register_hook


@register_hook("posttooluse", name="log_tools", priority=50)
def log_tool_usage(context):
    print(f"[{context.get('tool_name')}] -> {str(context.get('result'))[:100]}")
```

Valid hook points: `userpromptsubmit`, `pretooluse`, `posttooluse`, `stop`.

---

## Current Limits

- Formula decomposition is LLM-guided. There is no deterministic formula parser yet.
- Section, paragraph, and equation annotations require available source text or reliable retrieved evidence.
- The Google Scholar workflow depends on an external `scholar` CLI and its authentication state.
- `run_bash` currently uses `shell=True`; do not expose this runtime to untrusted users without sandboxing.
- The project does not yet include tests or CI.
- Some multi-agent tools are experimental and need more coverage before production use.

---

## Roadmap

- [ ] Sandboxed command execution for `run_bash`
- [ ] Unit tests for tool registration, prompt assembly, memory, compaction, scheduler, and task DAG behavior
- [ ] Integration tests with mocked Anthropic-compatible API calls
- [ ] CI for linting, type checking, and tests
- [ ] ArXiv, Semantic Scholar, Zotero, and PDF text extraction skills
- [ ] Stronger evidence tracking for section-level annotations
- [ ] Local web UI for non-CLI users
- [ ] PyPI publishing workflow

---

## Development

```bash
uv sync
uv run ruff check
uv run clearink
```

Contributions are welcome while the project is in alpha:

1. Fork the repository.
2. Create a feature branch.
3. Keep changes focused and run `uv run ruff check`.
4. Open a pull request with a short description of behavior and risk.

Issues and discussions are tracked on [GitHub](https://github.com/Mr-remon219/ClearInk).

---

## License

MIT License. See [LICENSE](LICENSE).

Copyright (c) 2026 Mr_Remon

---

*ClearInk — clear ink. Each formula clarified, each prerequisite traced, each path to understanding made visible.*
