<p align="center">
  <a href="http://47.93.166.221:8080/"><samp>ClearInk</samp></a>
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

**ClearInk** is a dual-mode academic reading agent.

**Mode 1** (default) — you give it a paper title and a formula you don't understand. It decomposes the formula, verifies citation metadata through Google Scholar, and returns a prerequisite reading path with specific section, paragraph, or equation references.

**Mode 2** — you ask a question about a paper's content. It gives a brief answer, then recommends prerequisite papers for deeper understanding.

Switch modes anytime with ``/mode 1`` or ``/mode 2``.

**Step mode** (``/step``) breaks responses into stages — overall explanation → paper route → per-paper details — so you can digest each step before continuing with ``/next`` or starting fresh with ``/end``.

ClearInk ships with a Rich terminal interface — a lemon pixel-art welcome screen, mode-aware prompts, spinner feedback, and Markdown rendering — styled after the clean CLI aesthetics of modern developer tools.

Under the hood, ClearInk is built on a compact Python agent runtime that includes: an Anthropic-compatible CLI loop, decorator-registered tools, ``SKILL.md`` skill extensions, persistent memory, hooks, sub-agents, a teammate system with protocol communication and git worktree isolation, MCP client for academic search (ModelScope, Semantic Scholar / Crossref), cron scheduling, context compaction, error recovery, and a Django-friendly API bridge.

The project is currently in **alpha**. The citation policy is strict by design: paper metadata must come from `scholar --bibtex` or `scholar cite`; missing fields should be reported as unavailable, not guessed. Section-level annotations are only as strong as the retrieved evidence available to the agent.

---

## Why ClearInk Exists

Reading a research paper is rarely linear. To give a simple example: when a computer science paper uses

```text
D(X+Y) = D(X) + D(Y) + 2Cov(X,Y)
```

the paper may assume that you already know the covariance expansion, the notation conventions, and the proof context. Following that trail manually can turn into hours of citation chasing. General-purpose LLMs often fill the gaps from memory and produce plausible but wrong titles, years, authors, or page references.

ClearInk treats paper reading as a dependency problem — identify the pieces of a formula, search for the prerequisite papers that introduced or explained them, rank those sources by dependency depth, and present a reading path with verified metadata and explicit uncertainty.

---

## What's Included

### Interaction

- **Rich terminal interface** — pixel-art lemon welcome screen, mode-aware prompts, spinner feedback, and Markdown rendering via `rich`.
- **Dual-mode interaction** — ``/mode 1`` for formula dependency analysis, ``/mode 2`` for paper Q&A. Switch anytime without restarting.
- **Step-by-step output** — ``/step`` breaks responses into stages; ``/next`` continues, ``/end`` starts a new round.

### Toolchain

- **Google Scholar skill** — on-demand citation lookup with hard rules to verify metadata through the `scholar` CLI.
- **MCP academic search** — connect to ModelScope, Semantic Scholar, and Crossref for verified paper search and metadata retrieval.
- **29 registered tools** — shell execution, file I/O, glob search, skills, memory, todos, DAG tasks, background tasks, sub-agents, teammate management, MCP client, git worktree management, and cron jobs.

### Agent Runtime

- **System prompt assembly** — builds prompts from `data/system_prompts/` templates, available skills, memories, and runtime environment.
- **Teammate system** — four-stage protocol communication with idle polling, autonomous task claiming, and git worktree isolation.
- **Reading hooks & audit log** — citation-verification reminders, paper-access tracking, and JSONL audit logging.
- **Persistent memory** — Markdown + YAML frontmatter store for user preferences and project knowledge.
- **Context compaction** — L1–L4 compression: trim, placeholder, archive, and summarize for long-running sessions.
- **Error recovery** — retries for transient API errors, context-overflow handling, and truncation recovery.

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
          14 hook points   frontmatter MD    retry/overflow/truncation
               |                |                |
               +----------------+----------------+
                                |
                          Agent loop
                                |
        +-----------+-----------+-----------+-----------+
        |           |           |           |           |
    Tool registry  Skills   Sub-agents   Teammates   Scheduler
    @register      SKILL.md  delegate     team/       cron
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
- **Citation discipline** — same citation verification and anti-hallucination rules from Mode 1 apply.

Example Mode 2 prompt:

```text
Mode 2 · Paper Q&A  (/mode 1 to switch)

Paper title: BERT: Pre-training of Deep Bidirectional Transformers
Your question about the paper: Why does BERT use layer normalization before the attention sub-layer instead of after?
```

---

## Runtime Features

| Component | Role | Use Cases |
|-----------|------|-------------|
| `@register_tool` | Decorator-based tool registry with JSON Schema-style tool definitions | Building extensible agent tools |
| `SKILL.md` loader | Dynamic skill discovery from `data/skills/*/SKILL.md` frontmatter | Domain-specific behavior without code changes |
| Sub-agent delegation | Lightweight model sub-agent with thinking disabled and up to 5 tool turns | Cheap parallel lookup or file-reading tasks |
| Teammate system | Background threads with protocol communication, idle polling, autonomous task claiming, and git worktree isolation | Multi-agent research workflows |
| MCP Client | Stdio JSON-RPC client; connect to external tool servers and dynamically register their tools | Academic search (ModelScope, Semantic Scholar, Crossref) |
| DAG task system | Dependency-resolved task graph with claim/complete/unblock flow | Research planning and workflow tracking |
| Context compaction | L1-L4 compression for long conversations | Long-running sessions under token limits |
| Error recovery | Retry, context overflow recovery, and truncation retry handling | More resilient API calls |
| Hook system | 14 hook points covering session, mode, MCP, teammate, task, and API lifecycle events + built-in JSONL audit log | Logging, policy reminders, reading context, and system auditing |
| Persistent memory | Markdown + YAML frontmatter memory store | User preferences and project knowledge |
| Cron scheduler | 5-field cron jobs persisted to JSON | Recurring research prompts |

---

## Quick Start

### Step 1: Install

**Prerequisites:** Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Mr-remon219/ClearInk.git
cd ClearInk
uv sync
```

### Step 2: Configure

Copy the environment template and edit it with your own values:

```bash
# macOS / Linux
cp data/environment/.env.sample data/environment/.env

# Windows (Command Prompt)
copy data\environment\.env.sample data\environment\.env
```

Open `data/environment/.env` in any text editor. The only three fields you **must** fill in:

```env
ANTHROPIC_API_KEY=<your-api-key>
ANTHROPIC_BASE_URL=<your-api-endpoint>
MODEL=<your-model-name>
```

All other variables (thinking controls, sub-agent model, path overrides) are
optional — their defaults and descriptions are documented inside `.env.sample`.

### Step 3: Run

```bash
uv run clearink
```

If you see a lemon pixel-art welcome screen, you're all set. From there:

```text
  Mode 1 · Formula Analysis  (/mode 2 to switch)

Paper title: Attention Is All You Need
Formula number or description: scaled dot-product attention formula

  Analyzing...
```

After the first answer you can ask follow-up questions, switch modes with
`/mode 1` or `/mode 2`, or exit with `/exit`.

### Optional Setup

**Google Scholar (citation verification):**

```bash
command -v scholar
scholar auth
```

**Advanced — custom data paths:**
Set `CLEARINK_DATA_DIR` before startup to relocate `.env`, logs, memories,
tasks, and MCP config into a single explicit directory. Set
`CLEARINK_REPO_ROOT` when the working directory differs from the Git repository
that ClearInk should manage (required for worktree operations).

---

## Project Structure

```text
ClearInk/
├── pyproject.toml
├── README.md
├── README_zh.md
├── LICENSE
├── data/
│   ├── environment/
│   │   ├── .env.sample          configuration template (commit-safe)
│   │   └── .env                 runtime API configuration, not committed
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
    ├── api/                    Django-friendly pure-Python API bridge
    ├── context_compact/        L1-L4 compaction
    ├── error_recovery/         retry, overflow, truncation
    ├── hook/                   pluggable hooks, reading hooks, audit log
    ├── message/                content block serialization and text extraction
    ├── system_prompt/          prompt assembly and memory
    ├── tool/                   registered tools (each in its own sub-package)
    │   ├── basetool/           bash, file, glob
    │   ├── background/         background task execution
    │   ├── mcp_client/         MCP stdio JSON-RPC client
    │   ├── scheduler/          cron job scheduling
    │   ├── skill/              SKILL.md loader
    │   ├── subagent/           synchronous sub-agent delegation
    │   ├── task_system/        DAG task management
    │   ├── team/               teammate system (protocol, idle, worktree)
    │   └── todo/               flat TODO list
    └── user/                   Rich CLI interface
        ├── console.py          console theme and lemon pixel art
        ├── interface.py        interactive prompt loop
        ├── mode.py             mode state, step mode, and command detection
        └── output_format.py    LaTeX to plain-text conversion
```

Some `data/` subdirectories are created at runtime and may not exist until the app runs for the first time.

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

Make sure this module is imported at startup so the decorator runs (for example, reference it in `clearink.tool.__init__`).

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

Valid hook points: ``userpromptsubmit``, ``pretooluse``, ``posttooluse``, ``stop``, ``session_created``, ``session_destroyed``, ``mode_switched``, ``step_mode_changed``, ``mcp_connected``, ``mcp_disconnected``, ``teammate_spawned``, ``teammate_stopped``, ``task_lifecycle``, ``api_request``.

---

## Current Limits

- Formula decomposition is LLM-guided — there is no deterministic formula parser yet.
- Section, paragraph, and equation annotations require accessible source text or reliable retrieved evidence.
- The Google Scholar workflow depends on an external `scholar` CLI and its authentication state.
- `run_bash` currently uses `shell=True`; sandbox before exposing to untrusted users.
- Some multi-agent features are experimental and need more testing before production use.

---

## Roadmap

- [ ] Sandboxed command execution for `run_bash`
- [x] Unit tests for core output formatting and thinking replay behavior
- [x] Integration tests with mocked Anthropic-compatible API calls
- [ ] CI for linting, type checking, and tests
- [x] ArXiv, Semantic Scholar paper search (MCP integration)
- [ ] Zotero and PDF text extraction skills
- [ ] Stronger evidence tracking for section-level annotations
- [ ] Browser-based web UI
- [ ] PyPI publishing workflow

---

## Development

```bash
uv sync
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run clearink
```

Contributions are welcome while the project is in alpha:

1. Fork the repository.
2. Create a feature branch.
3. Keep changes focused — run `uv run --no-sync pytest` and `uv run --no-sync ruff check .` before submitting.
4. Open a pull request with a short description of behavior and risk.

Issues and discussions are tracked on [GitHub](https://github.com/Mr-remon219/ClearInk).

---

## License

MIT License. See [LICENSE](LICENSE).

Copyright (c) 2026 Mr_Remon

---

*ClearInk — clear ink. Each formula clarified, each prerequisite traced, each path to understanding made visible.*
