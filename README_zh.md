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

## 推荐使用方式

遇到小而具体的问题，可以直接问 ChatGPT、Gemini、Claude、DeepSeek 等通用大模型。

当你感觉某个知识点不是一句话能解释清楚，而是需要系统学习、需要知道“该先读什么、再读什么”时，使用 **ClearInk**。ClearInk 会帮你追溯前置论文、概念依赖和具体阅读位置；之后你再回到 ChatGPT、Gemini、Claude、DeepSeek 等模型继续提问，会更有方向。

```text
小问题 -> ChatGPT / Gemini / Claude / DeepSeek
需要系统学习的知识点 -> ClearInk -> ChatGPT / Gemini / Claude / DeepSeek
```

---

**ClearInk**（清砚）是一个运行在 Rich 终端里的学术阅读 agent，目标不是替代通用聊天模型，而是帮你系统地找到“为了理解这个公式/概念，我应该先读什么”。你给它一篇论文标题，再给一个公式、概念，或描述自己卡住的地方，它会尝试拆解前置知识、追溯相关论文，并在证据允许时给出具体阅读位置。

例如你输入“Attention Is All You Need 里的公式 (12)”。ClearInk 会把公式拆成符号、运算符和隐含概念，构造成依赖任务图；可并行的查找会交给队友 agent 同时执行；引用元数据通过学术搜索工具验证；最后输出按依赖深度组织的阅读路线。查不到的字段不会硬编，而是标为不可用。

ClearInk 当前的主要体验是命令行引导：首次启动配置向导、模式选择、每轮可选的 step 分步输出、Markdown 渲染、柠檬像素欢迎画面。底层是一套紧凑的 Python agent 运行时：工具注册、DAG 任务系统、并行队友、lead 监管、sub-agent、MCP 学术搜索、上下文压缩和错误恢复。

项目目前处于 **alpha** 阶段，引用验证规则刻意从严。

---

## ClearInk 解决什么问题

读论文很少是线性的。一个公式背后可能隐含符号约定、前置推导、证明上下文，以及好几篇论文里的概念。手动追溯这些依赖很耗时间，而通用大模型又可能凭印象补出看似合理但无法验证的标题、年份或作者。

ClearInk 把读论文看作依赖图问题：

- 拆解公式或概念中的前置知识；
- 搜索定义或解释这些知识的论文和资料；
- 按依赖深度组织阅读顺序；
- 在原文或可靠证据支持时，指出具体章节、段落或公式。

---

## 怎么做到的

### 两种阅读模式

- **Mode 1 - 公式/概念分析**：从论文标题和公式、公式编号或已知概念出发，拆解并构建前置阅读拓扑。
- **Mode 2 - 描述不会的地方**：用户用自然语言描述卡住的问题，ClearInk 先识别核心知识缺口，再映射到前置概念和论文。

### 硬编码并行调度

lead agent 把工作建模成一个**任务 DAG**。每轮可以调用 `auto_dispatch()`，这条规则写在代码里：

- **0 个可执行任务** -> 等待队友结果或检查依赖
- **1 个可执行任务** -> lead 自己直接做，避免队友开销
- **2 个以上可执行任务** -> 自动调用 `execute_parallel()` 并 spawn 队友

队友通过 JSONL inbox 接收显式任务分配，完成后向 lead 汇报，短暂等待后续任务，然后退出。队友不会自主抢任务。lead 通过 `regulate_teammates()`、`inspect_teammate()`、`reject_and_reassign()`、`audit_stranded_tasks()` 进行监督和质量控制。

队友内部还可以调用 `spawn_subagent` 处理更小的并行检查，例如同时验证多篇引用。队友和 sub-agent 共用同一个 LLM 工具循环。

---

## 包含什么

### 交互

- **Rich 终端界面** — 首次配置向导、语言选择、柠檬欢迎画面、spinner 等待、Markdown 渲染。
- **两种模式** — 公式/概念分析，以及“描述不会的地方”。
- **Step 分步输出** — 每轮开始可选择 `/step`；用 `/next` 继续；用 `/end` 开启新一轮。

### 工具链

- **Google Scholar 工作流** — 在可用时通过外部 `scholar` CLI 验证元数据。
- **MCP 学术搜索** — 通过 `data/mcp/servers.json` 配置，并在运行时合并进模型可用工具。
- **24 个注册工具** — shell、文件、glob、DAG 任务、队友管理、auto-dispatch、regulation、sub-agent、MCP 连接。

### Agent 运行时

- **系统提示词装配** — 由 `data/system_prompts/guidelines.md` 构建，模式指令注入到用户消息中。
- **DAG 任务系统** — 任务按依赖执行并持久化为 JSON；完成任务可保存简短结果证据。
- **队友系统** — 显式分配、JSONL 消息总线、短暂 linger、lead 监督。
- **上下文与 token 处理** — 大文本占位、L4 摘要、上下文溢出恢复、输出截断重试、非 thinking 请求的历史 thinking 清理。
- **阅读钩子** — 引用请求检测、论文访问追踪、任务生命周期追踪。
- **API 桥接层** — 提供可嵌入其他应用的 Python session/endpoints；主要用户体验仍是 CLI。

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

首次运行 CLI 时会通过配置向导生成 `data/environment/.env`。向导会询问 API key 和输出语言，并写入 DeepSeek 兼容端点的默认配置。

如果你想手动配置，创建 `data/environment/.env` 并填入：

```env
ANTHROPIC_API_KEY=<your-api-key>
ANTHROPIC_BASE_URL=<your-api-endpoint>
MODEL=<your-model-name>
```

可选：`THINKING_TYPE`、`THINKING_BUDGET`、`THINKING_EFFORT`、`SUBAGENT_MODEL`、`TEAMMATE_LINGER_SECONDS`、`CLEARINK_LANG`、`CLEARINK_DATA_DIR`、`CLEARINK_REPO_ROOT`。

### 3. 运行

```bash
uv run clearink
```

启动后会看到 ClearInk 欢迎界面。一轮典型输入如下：

```text
选择模式：
  [1] 公式/概念分析
  [2] 有不会的请描述给我

论文标题：Attention Is All You Need
公式编号或描述：scaled dot-product attention formula
按回车开始，或输入 /step 启用分步输出
```

---

## 架构

```text
                         clearink CLI
                              |
                   Rich 终端交互界面
                              |
               模式 + 论文 + 公式/问题
                              |
               系统提示词 + 模式指令
                              |
                        Agent 循环
                              |
      +-----------+-----------+-----------+-----------+
      |           |           |           |           |
   工具注册表   Sub-agent   队友系统   Regulation  MCP 客户端
   (24个工具)  _llm_loop   team/      regulation/ mcp_client/
      |
      +---- DAG 任务系统 + auto_dispatch + JSON 运行态
                              |
                 上下文压缩 + 错误恢复
```

---

## 项目结构

```text
ClearInk/
├── pyproject.toml
├── README.md / README_zh.md
├── data/
│   ├── environment/.env          运行时配置，由首次启动向导创建
│   ├── system_prompts/
│   │   ├── guidelines.md         通用系统指引
│   │   ├── mode1.md              公式/概念模式指令
│   │   └── mode2.md              描述困惑模式指令
│   ├── skills/google_scholar/    Scholar 工作流说明
│   ├── mcp/servers.json          MCP server 配置
│   ├── .tasks/                   任务 JSON，gitignored
│   ├── .transcripts/             压缩归档，gitignored
│   ├── task_outputs/             任务输出产物，gitignored
│   ├── team/                     队友 inbox 文件，gitignored
│   ├── logs/                     运行日志，gitignored
│   └── papers/                   下载的 PDF/文本，gitignored
└── src/clearink/
    ├── main.py                   入口 + agent 循环
    ├── api/                      可嵌入的 Python API 桥接层
    ├── context_compact/          L2 占位 + L4 摘要
    ├── error_recovery/           重试 / 溢出 / 截断恢复
    ├── hook/                     钩子系统 + 阅读处理
    ├── message/                  内容块序列化
    ├── system_prompt/            提示词装配
    ├── tool/                     工具、任务、队友、MCP、监管
    └── user/
        ├── interface.py          Rich CLI 流程和首次启动配置
        ├── mode.py               模式选择与输入收集
        ├── i18n.py               UI 多语言文案
        └── output_format.py      Markdown / step 输出格式化
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

- 公式和概念拆解依赖 LLM 判断，还没有确定性公式解析器。
- 章节、段落、公式编号推荐需要可获取的原文或可靠证据支持。
- Google Scholar 元数据验证依赖外部 `scholar` CLI 及其本地配置/认证状态。
- 学术 MCP server 可能需要本地配置或网络可用性。
- 多 agent 执行仍属实验性质，目标是加速，但队友结果仍需要 lead 审查。

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
