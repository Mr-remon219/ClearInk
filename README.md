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

**ClearInk** is an academic reading agent. You give it a paper title and a formula you don't understand — it tells you exactly which papers to read first, down to the specific section or paragraph.

For example: "Eq. (12) in Attention Is All You Need." ClearInk decomposes the formula into every symbol and operator, builds a dependency graph tracing each concept back to its source paper, verifies everything through Google Scholar, and returns a ranked reading path. Metadata is never fabricated — if a field is missing from BibTeX, it's reported as unavailable.

ClearInk runs in a Rich terminal with a lemon pixel-art welcome screen, mode-aware prompts, and Markdown rendering. Under the hood it's a focused Python agent runtime: decorator-registered tools, a DAG task system, parallel teammates with explicit dispatch, a Regulation module for supervision, sub-agents for sub-task acceleration, an MCP client for academic search, context compaction, and error recovery.

The project is in **alpha**. Citations are strict by design.

---

## Why ClearInk Exists

Reading a research paper is rarely linear. When a paper writes

```text
D(X+Y) = D(X) + D(Y) + 2Cov(X,Y)
```

it assumes you already know the covariance expansion, the notation conventions, and the proof context. Tracing that trail manually can take hours. General-purpose LLMs often fill the gaps from memory, producing plausible but wrong titles, years, or authors.

ClearInk treats paper reading as a dependency problem: identify each piece of a formula, find the papers that introduced or explained those pieces, rank them by dependency depth, and present a reading path backed by verified metadata.

---

## How It Works

### The hard rule: 1 task = do it yourself, 2+ = go parallel

The lead agent models the formula as a **task DAG**. Each turn it calls `auto_dispatch()`, which enforces a single rule in code — not buried in a prompt:

- **0 unblocked tasks** → wait for teammates or check dependencies
- **1 unblocked task** → the lead executes it directly, no teammate overhead
- **2+ unblocked tasks** → automatically spawns teammates for parallel execution

Teammates are daemon threads that receive explicitly assigned tasks through a JSONL message bus. They work, report results, linger 10 seconds for follow-up assignments, then exit. No idle polling, no autonomous task claiming — all work is explicitly dispatched.

The lead supervises via the **Regulation module**: `regulate_teammates()` to see who's working on what, `inspect_teammate()` to review output, `reject_and_reassign()` to kill bad results and reassign, and `audit_stranded_tasks()` as a safety net for anything that slips through.

Teammates can call `spawn_subagent` internally to parallelize further — verifying three citations at once, for example. Both teammates and sub-agents share a single LLM tool loop (`_llm_loop.py`).

---

## What's Included

### Interaction

- **Rich terminal** — pixel-art lemon welcome, spinner feedback, Markdown rendering.
- **Step-by-step output** — `/step` breaks responses into stages; `/next` continues, `/end` restarts.

### Toolchain

- **Google Scholar** — citation lookup with hard rules to verify metadata through the `scholar` CLI.
- **MCP academic search** — ModelScope, Semantic Scholar, Crossref for verified paper search.
- **24 registered tools** — bash, file I/O, glob, DAG tasks, sub-agents, teammate management, auto-dispatch, regulation, MCP client.

### Agent Runtime

- **System prompt** — built from a single compressed `guidelines.md`.
- **Teammate system** — simplified WORK → LINGER → EXIT lifecycle, explicit dispatch via `assign_task_to_teammate` and `execute_parallel`, JSONL message bus, shutdown-only protocol.
- **Regulation module** — 4 lead-only tools for parallel execution supervision, backed by `ExecutionTracker` with dual-index in-memory state.
- **DAG task system** — dependency-resolved graph with write-through JSON persistence.
- **Shared LLM loop** — `_llm_loop.py` used by both teammates and sub-agents, grouping all response blocks into a single assistant message.
- **Reading hooks** — citation-verification reminders and paper-access tracking.
- **Context compaction** — L2 (placeholder replacement) + L4 (summarization); L1 and L3 removed.
- **Error recovery** — retry, context-overflow handling, truncation recovery.

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

```bash
cp data/environment/.env.sample data/environment/.env
```

Fill in `data/environment/.env`:

```env
ANTHROPIC_API_KEY=<your-api-key>
ANTHROPIC_BASE_URL=<your-api-endpoint>
MODEL=<your-model-name>
```

Optional: `THINKING_TYPE`, `THINKING_BUDGET`, `THINKING_EFFORT`, `SUBAGENT_MODEL`, `TEAMMATE_LINGER_SECONDS`.

### 3. Run

```bash
uv run clearink
```

You should see a lemon pixel-art welcome screen. Then:

```text
  Mode 1 · Formula Analysis

Paper title: Attention Is All You Need
Formula number or description: scaled dot-product attention formula
```

---

## Architecture

```text
                         clearink CLI
                              |
                   Rich terminal interface
                              |
                   Paper title + formula
                              |
              System prompt (guidelines.md)
                              |
                        Agent loop
                              |
      +-----------+-----------+-----------+-----------+
      |           |           |           |           |
  Tool registry  Sub-agents  Teammates  Regulation  MCP Client
  (24 tools)     _llm_loop   team/      regulation/ mcp_client/
      |
+-----+-----+-----+-----+-----+-----+
|     |     |     |     |     |     |
bash file glob task auto_  regu-  ...
                   dispatch late
                              |
             Context compaction (L2+L4)
```

---

## Project Structure

```text
ClearInk/
├── pyproject.toml
├── README.md / README_zh.md
├── data/
│   ├── environment/.env          runtime config (not committed)
│   ├── system_prompts/
│   │   ├── guidelines.md         system prompt
│   │   └── mode1.md              mode 1 instructions
│   ├── .tasks/                   DAG task persistence
│   ├── .transcripts/             compaction archives
│   └── team/                     teammate inbox files
└── src/clearink/
    ├── main.py                   entry point + agent loop
    ├── api/                      Django-friendly API bridge
    ├── context_compact/          L2 + L4 compaction
    ├── error_recovery/           retry / overflow / truncation
    ├── hook/                     hooks + reading handlers
    ├── message/                  content block serialization
    ├── system_prompt/            prompt assembly
    ├── tool/
    │   ├── _llm_loop.py          shared LLM tool-use loop
    │   ├── basetool/             bash, file, glob
    │   ├── mcp_client/           MCP stdio JSON-RPC
    │   ├── regulation/           lead supervision tools
    │   ├── subagent/             sub-agent delegation
    │   ├── task_system/          DAG task management
    │   └── team/                 teammates + bus + tracker
    └── user/                     Rich CLI interface
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

- Formula decomposition is LLM-guided — no deterministic formula parser yet.
- Section and equation annotations need accessible source text or reliable evidence.
- The Google Scholar workflow depends on an external `scholar` CLI and its auth state.
- Some multi-agent features are experimental.

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
