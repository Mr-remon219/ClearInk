<p align="center">
  <a href="http://47.93.166.221:8080/"><samp>ClearInk</samp></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/build-uv-f7df1e?style=flat-square" alt="uv build">
  <img src="https://img.shields.io/badge/status-alpha-999?style=flat-square" alt="Alpha">
</p>

<p align="center">
  <sub><a href="README.md">English</a> | <a href="README_zh.md">简体中文</a></sub>
</p>

---

## Recommended Use

Use general-purpose LLMs such as ChatGPT, Gemini, Claude, or DeepSeek for small, isolated questions.

Use **ClearInk** when a concept feels large enough that you need a structured learning path: ClearInk helps trace the prerequisite papers, concepts, and sections you should study first. After that, you can return to ChatGPT, Gemini, Claude, DeepSeek, or another model with a clearer map of what to ask.

```text
Small question -> ChatGPT / Gemini / Claude / DeepSeek
Systematic learning gap -> ClearInk -> ChatGPT / Gemini / Claude / DeepSeek
```

---

**ClearInk** is a Rich-terminal academic reading agent for prerequisite paper pathfinding. It is not trying to be a general chatbot. You give it a paper title plus a formula, concept, or point of confusion; it helps identify what you need to understand first, which papers explain those prerequisites, and where to read inside those papers.

For example: "Eq. (12) in Attention Is All You Need." ClearInk decomposes the formula into symbols, operators, and assumed concepts, turns the work into a dependency-aware task graph, dispatches independent lookups in parallel, verifies citation metadata through academic search tools, and returns a reading path with section-level guidance when evidence is available.

ClearInk currently runs primarily as a guided command-line experience: a first-run setup wizard, mode-aware prompts, optional step-by-step output, Markdown rendering, and a lemon pixel-art welcome screen. Under the hood it is a focused Python agent runtime with decorator-registered tools, a DAG task system, parallel teammates, lead-side regulation, sub-agents, MCP academic search, context compaction, and API-call recovery.

The project is in **alpha**. Citation metadata must be verified; missing metadata should be reported as unavailable, not inferred.

---

## Why ClearInk Exists

Reading a research paper is rarely linear. A formula may assume notation conventions, earlier derivations, proof context, and several papers' worth of prior concepts. Tracing that path manually can take hours, while general-purpose LLMs can easily produce plausible but unverifiable titles, years, or authors.

ClearInk treats paper reading as a dependency problem:

- break the formula or concept into smaller prerequisite units;
- search for papers or sources that define or explain those units;
- rank the results by dependency depth;
- point the user to the relevant sections, paragraphs, or equations when the source text supports it.

---

## How It Works

### Two Reading Modes

- **Mode 1 - Formula / Concept Analysis**: start from a paper title and a formula, equation number, or known concept. ClearInk decomposes the target and builds a prerequisite topology.
- **Mode 2 - Describe Your Confusion**: start from a natural-language description of what you do not understand. ClearInk first identifies the core knowledge gap, then maps it to prerequisite concepts and papers.

### Hard-coded Parallel Dispatch

The lead agent models work as a **task DAG**. Each turn it can call `auto_dispatch()`, which enforces a code-level rule:

- **0 unblocked tasks** -> wait for teammate results or inspect dependencies
- **1 unblocked task** -> the lead executes it directly, avoiding teammate overhead
- **2+ unblocked tasks** -> ClearInk automatically calls `execute_parallel()` and spawns teammates

Teammates receive explicit task assignments through JSONL inbox files, report results back to the lead, linger briefly for follow-up work, then exit. They do not autonomously claim tasks. The lead remains supervisor and quality gate through `regulate_teammates()`, `inspect_teammate()`, `reject_and_reassign()`, and `audit_stranded_tasks()`.

Teammates can use `spawn_subagent` for smaller independent checks, such as verifying several citations in parallel. Both teammates and sub-agents share the same LLM tool-use loop.

---

## What's Included

### Interaction

- **Rich terminal interface** - first-run setup wizard, language selection, lemon welcome screen, spinner feedback, Markdown rendering.
- **Two modes** - formula/concept analysis and "describe your confusion."
- **Step-by-step output** - choose `/step` for the current round, use `/next` to continue, and `/end` to start a fresh round.

### Toolchain

- **Google Scholar workflow** - metadata verification through the external `scholar` CLI when available.
- **MCP academic search** - configured through `data/mcp/servers.json`, with tools merged into the model tool pool at runtime.
- **24 registered tools** - shell/file/glob helpers, DAG tasks, teammate management, auto-dispatch, regulation, sub-agents, and MCP connection.

### Agent Runtime

- **System prompt assembly** - built from `data/system_prompts/guidelines.md`, with mode instructions injected into user messages.
- **DAG task system** - dependency-resolved tasks persisted as JSON; completed tasks may store concise result evidence.
- **Teammate system** - explicit assignment, JSONL message bus, short linger window, lead-side supervision.
- **Context and token handling** - large-content placeholdering, L4 summarization, context-overflow recovery, output truncation retry, and non-thinking replay sanitization.
- **Reading hooks** - citation-request detection, paper-access tracking, and task lifecycle tracking.
- **API bridge** - pure-Python session/endpoints layer for embedding ClearInk in another application, while the primary user experience remains the CLI.

---

## Quick Start

### 1. Install

Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/Mr-remon219/ClearInk.git
cd ClearInk
uv sync
```

### 2. Configure

The CLI creates `data/environment/.env` through a first-run setup wizard. The wizard asks for your API key and output language, then writes sensible DeepSeek-compatible defaults.

For manual setup, create `data/environment/.env` with:

```env
ANTHROPIC_API_KEY=<your-api-key>
ANTHROPIC_BASE_URL=<your-api-endpoint>
MODEL=<your-model-name>
```

Optional: `THINKING_TYPE`, `THINKING_BUDGET`, `THINKING_EFFORT`, `SUBAGENT_MODEL`, `TEAMMATE_LINGER_SECONDS`, `CLEARINK_LANG`, `CLEARINK_DATA_DIR`, `CLEARINK_REPO_ROOT`.

### 3. Run

```bash
uv run clearink
```

You should see the ClearInk welcome screen. A typical round looks like:

```text
Select mode:
  [1] Formula / Concept Analysis
  [2] Describe Your Confusion

Paper title: Attention Is All You Need
Formula number or description: scaled dot-product attention formula
Press Enter to start, or type /step for step-by-step output
```

---

## Architecture

```text
                         clearink CLI
                              |
                   Rich terminal interface
                              |
               Mode + paper + formula/question
                              |
              System prompt + mode instructions
                              |
                        Agent loop
                              |
      +-----------+-----------+-----------+-----------+
      |           |           |           |           |
  Tool registry  Sub-agents  Teammates  Regulation  MCP Client
  (24 tools)     _llm_loop   team/      regulation/ mcp_client/
      |
      +---- DAG task system + auto_dispatch + JSON runtime state
                              |
             Context compaction + error recovery
```

---

## Project Structure

```text
ClearInk/
├── pyproject.toml
├── README.md / README_zh.md
├── data/
│   ├── environment/.env          runtime config, created by setup wizard
│   ├── system_prompts/
│   │   ├── guidelines.md         shared system guidance
│   │   ├── mode1.md              formula/concept mode instructions
│   │   └── mode2.md              describe-confusion mode instructions
│   ├── skills/google_scholar/    Scholar workflow instructions
│   ├── mcp/servers.json          MCP server configuration
│   ├── .tasks/                   task JSON files, gitignored
│   ├── .transcripts/             compaction archives, gitignored
│   ├── task_outputs/             task output artifacts, gitignored
│   ├── team/                     teammate inbox files, gitignored
│   ├── logs/                     runtime logs, gitignored
│   └── papers/                   downloaded PDFs/text, gitignored
└── src/clearink/
    ├── main.py                   entry point + agent loop
    ├── api/                      embeddable Python API bridge
    ├── context_compact/          L2 placeholdering + L4 summaries
    ├── error_recovery/           retry / overflow / truncation recovery
    ├── hook/                     hooks + reading handlers
    ├── message/                  content block serialization
    ├── system_prompt/            prompt assembly
    ├── tool/                     tools, tasks, teammates, MCP, regulation
    └── user/
        ├── interface.py          Rich CLI flow and first-run setup
        ├── mode.py               mode selection and prompt collection
        ├── i18n.py               UI language strings
        └── output_format.py      Markdown / step output formatting
```

---

## Extending

### Add a Tool

```python
from clearink.tool.register import register_tool

@register_tool(
    name="arxiv_search",
    description="Search ArXiv by keyword",
    input_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)
def arxiv_search(query: str) -> str:
    return f"Results for: {query}"
```

Import the module in `main.py` so the decorator fires at startup.

### Add a Hook

```python
from clearink.hook.hook import register_hook

@register_hook("posttooluse", name="log_tools", priority=50)
def log_tool_usage(context):
    print(f"[{context.get('tool_name')}] -> {str(context.get('result'))[:100]}")
```

Valid hook points: `userpromptsubmit`, `pretooluse`, `posttooluse`, `stop`, `mode_switched`, `mcp_connected`, `teammate_spawned`, `teammate_stopped`, `task_lifecycle`.

---

## Current Limits

- Formula and concept decomposition is LLM-guided; there is no deterministic formula parser yet.
- Section, paragraph, and equation recommendations require accessible source text or reliable evidence.
- Google Scholar metadata verification depends on the external `scholar` CLI and its local auth/setup state.
- Academic MCP servers may require local configuration or network availability.
- Multi-agent execution is experimental and optimized for speed, but teammate outputs still need lead-side review.

---

## Development

```bash
uv sync
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run clearink
```

Contributions welcome during alpha. Fork, branch, keep changes focused, open a PR.

---

## License

MIT License. See [LICENSE](LICENSE).

Copyright (c) 2026 Mr_Remon
