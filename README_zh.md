<p align="center">
  <a href="http://47.93.166.221:8080/"><samp>清砚 / ClearInk</samp></a>
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

**ClearInk**（清砚）是一个学术阅读 agent。给它一篇论文标题和你没看懂的公式，它告诉你该先去读哪些前置论文——精确到具体的章节或段落。

比如你输入"Attention Is All You Need 里的公式 (12)"。ClearInk 会把公式拆成每个符号和运算符，构建一张依赖图，追溯每个概念的来源论文，通过 Google Scholar 验证引用信息，最后返回一条按深度分级的阅读路径。引用元数据从不瞎编——BibTeX 里缺什么就直接标注为不可用。

ClearInk 运行在 Rich 终端里，有柠檬像素风格的欢迎画面、随模式变化的输入提示和 Markdown 渲染输出。底层是一套紧凑的 Python agent 运行时：装饰器注册的工具、DAG 任务系统、显式调度的并行队友、用于监管的 Regulation 模块、用于子任务加速的 sub-agent、对接学术搜索的 MCP 客户端、上下文压缩和错误恢复。

项目目前处于 **alpha** 阶段，引用规则设计上就刻意从严。

---

## ClearInk 解决什么问题

读论文很少是线性的。当一篇论文写出

```text
D(X+Y) = D(X) + D(Y) + 2Cov(X,Y)
```

它假定你已经知道协方差的展开式、符号惯例和证明上下文。手动追溯这些前置知识可能要花好几个小时。通用大语言模型往往凭记忆补全信息，给出看着合理实则错误的标题、年份或作者。

ClearInk 把读论文当成依赖图问题来处理：找出公式的每个组成部分，搜索引出或解释这些概念的前置论文，按依赖深度排序，给出可验证的阅读路径。

---

## 怎么做到的

### 硬编码规则：1 个任务自己做，2 个以上并行分发

lead agent 把公式建模成一个**任务 DAG**。每轮调用 `auto_dispatch()`，这条规则是写在代码里的，不是塞在 prompt 里：

- **0 个可执行任务** → 等待队友或检查依赖
- **1 个可执行任务** → lead 自己直接做，不浪费队友开销
- **2 个以上可执行任务** → 自动 spawn 队友并行执行

队友是后台守护线程。它们通过 JSONL 消息总线接收显式分配的任务，干活、回报结果、等待 10 秒看有没有后续任务分配、然后退出。没有空闲轮询，没有自主抢任务——所有工作都是显式分配的。

lead 通过 **Regulation 模块**监督并行执行：`regulate_teammates()` 看谁在干什么，`inspect_teammate()` 审查输出质量，`reject_and_reassign()` 否决差结果并重分配，`audit_stranded_tasks()` 兜底检查有没有遗漏的任务。

队友内部可以调用 `spawn_subagent` 进一步并行——比如同时校验三篇引用。队友和 sub-agent 共享同一个 LLM 工具循环（`_llm_loop.py`）。

---

## 包含什么

### 交互

- **Rich 终端** — 柠檬像素欢迎画面，spinner 等待，Markdown 渲染。
- **Step 分步输出** — `/step` 拆成多步回答；`/next` 继续，`/end` 重新开始。

### 工具链

- **Google Scholar** — 引用查询，通过 `scholar` CLI 验证元数据。
- **MCP 学术搜索** — 对接 ModelScope、Semantic Scholar、Crossref。
- **24 个注册工具** — bash、文件读写、glob、DAG 任务、sub-agent、队友管理、auto-dispatch、regulation、MCP 客户端。

### Agent 运行时

- **系统提示词** — 由一份精简的 `guidelines.md` 构建。
- **队友系统** — 简化生命周期（WORK → LINGER → EXIT），通过 `assign_task_to_teammate` 和 `execute_parallel` 显式分配，JSONL 消息总线，仅保留 shutdown 协议。
- **Regulation 模块** — 4 个 lead 专用监管工具，背后是双索引内存存储的 `ExecutionTracker`。
- **DAG 任务系统** — 依赖解析图，写穿式 JSON 持久化。
- **共享 LLM 循环** — `_llm_loop.py` 同时服务于队友和 sub-agent，将所有响应块合并为单条 assistant 消息。
- **阅读钩子** — 引用验证提醒和论文文件访问追踪。
- **上下文压缩** — L2（大文本占位替换）+ L4（摘要）；L1 和 L3 已移除。
- **错误恢复** — 重试、上下文溢出处理、截断恢复。

---

## 快速开始

### 1. 安装

需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)：

```bash
git clone https://github.com/Mr-remon219/ClearInk.git
cd ClearInk
uv sync
```

### 2. 配置

```bash
cp data/environment/.env.sample data/environment/.env
```

编辑 `data/environment/.env`，填入：

```env
ANTHROPIC_API_KEY=<your-api-key>
ANTHROPIC_BASE_URL=<your-api-endpoint>
MODEL=<your-model-name>
```

可选：`THINKING_TYPE`、`THINKING_BUDGET`、`THINKING_EFFORT`、`SUBAGENT_MODEL`、`TEAMMATE_LINGER_SECONDS`。

### 3. 运行

```bash
uv run clearink
```

看到柠檬像素欢迎画面就说明跑起来了：

```text
  Mode 1 · Formula Analysis

Paper title: Attention Is All You Need
Formula number or description: scaled dot-product attention formula
```

---

## 架构

```text
                         clearink CLI
                              |
                   Rich 终端交互界面
                              |
                    论文标题 + 公式
                              |
               系统提示词 (guidelines.md)
                              |
                        Agent 循环
                              |
      +-----------+-----------+-----------+-----------+
      |           |           |           |           |
   工具注册表   Sub-agent   队友系统   Regulation  MCP 客户端
   (24个工具)  _llm_loop   team/      regulation/ mcp_client/
      |
+-----+-----+-----+-----+-----+-----+
|     |     |     |     |     |     |
bash file glob task auto_  regu-  ...
                   dispatch late
                              |
               上下文压缩 (L2+L4)
```

---

## 项目结构

```text
ClearInk/
├── pyproject.toml
├── README.md / README_zh.md
├── data/
│   ├── environment/.env          运行时配置（不提交）
│   ├── system_prompts/
│   │   ├── guidelines.md         系统提示词
│   │   └── mode1.md              Mode 1 指令
│   ├── .tasks/                   DAG 任务持久化
│   ├── .transcripts/             压缩归档
│   └── team/                     队友收件箱文件
└── src/clearink/
    ├── main.py                   入口 + agent 循环
    ├── api/                      Django 友好的 API 桥接层
    ├── context_compact/          L2 + L4 压缩
    ├── error_recovery/           重试 / 溢出 / 截断
    ├── hook/                     钩子系统 + 阅读处理
    ├── message/                  内容块序列化
    ├── system_prompt/            提示词装配
    ├── tool/
    │   ├── _llm_loop.py          共享 LLM 工具循环
    │   ├── basetool/             bash、文件、glob
    │   ├── mcp_client/           MCP stdio JSON-RPC
    │   ├── regulation/           lead 监管工具
    │   ├── subagent/             sub-agent 委托
    │   ├── task_system/          DAG 任务管理
    │   └── team/                 队友 + 消息总线 + tracker
    └── user/                     Rich CLI 界面
```

---

## 扩展

### 添加工具

```python
from clearink.tool.register import register_tool

@register_tool(
    name="arxiv_search",
    description="按关键词搜索 ArXiv",
    input_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)
def arxiv_search(query: str) -> str:
    return f"Results for: {query}"
```

在 `main.py` 中导入该模块，让装饰器在启动时执行。

### 添加钩子

```python
from clearink.hook.hook import register_hook

@register_hook("posttooluse", name="log_tools", priority=50)
def log_tool_usage(context):
    print(f"[{context.get('tool_name')}] -> {str(context.get('result'))[:100]}")
```

可用的钩子点：`userpromptsubmit`、`pretooluse`、`posttooluse`、`stop`、`mode_switched`、`mcp_connected`、`teammate_spawned`、`teammate_stopped`、`task_lifecycle`。

---

## 当前局限

- 公式分解靠 LLM 判断，还没有确定性的公式解析器。
- 章节和公式标注需要有可获取的原文或可靠证据支持。
- Google Scholar 工作流依赖外部 `scholar` CLI 及其认证状态。
- 部分多 agent 功能仍属实验性质。

---

## 开发

```bash
uv sync
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run clearink
```

alpha 阶段欢迎贡献。Fork → 建分支 → 聚焦改动 → 提 PR。

---

## 许可证

MIT License。详见 [LICENSE](LICENSE)。

Copyright (c) 2026 柠檬山上的柠檬精
