<p align="center">
  <a href="http://47.93.166.221:8080/"><samp>清砚 / ClearInk</samp></a>
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

**ClearInk**（清砚）是一个双模式学术阅读 agent。在 **Mode 1**（默认模式）下，你提供论文标题和看不懂的公式，它会分解公式、通过 Google Scholar 验证引用元数据，并返回一条带有精确章节、段落或公式标注的前置阅读路径。在 **Mode 2** 下，你对论文内容提问，它会先给出简短解答，再推荐用于深入理解的前置论文。两种模式可以在会话中随时通过 ``/mode 1`` 或 ``/mode 2`` 切换。**Step 模式**（``/step``）将回答拆分为分步输出——总体解释 → 论文路线 → 逐篇详析——用户可以逐步消化，通过 ``/next`` 继续、``/end`` 开启新一轮提问。

ClearInk 配备了一个基于 Rich 库的终端界面——柠檬像素艺术欢迎画面、随模式变化的输入提示、spinner 等待动画以及 Markdown 渲染输出——整体风格参考了现代开发者工具的简洁 CLI 美学。

在底层，ClearInk 同时是一个紧凑的 Python agent 运行时：Anthropic 兼容的 CLI 循环、基于装饰器的工具注册、``SKILL.md`` 技能扩展、持久化记忆、钩子系统、子代理、完整的队友系统（协议通信、空闲轮询、任务认领、git worktree 隔离）、MCP 学术搜索客户端（ModelScope、Semantic Scholar / Crossref）、cron 调度、DAG 任务管理、上下文压缩、错误恢复，以及便于 Django 后端接入的 API 层。

项目目前处于 **alpha** 阶段。引用策略是刻意从严设计的：论文元数据必须来自 `scholar --bibtex` 或 `scholar cite`；缺失字段应如实报告为"不可用"而非猜测填充。章节级标注的精确程度取决于 agent 可检索到的证据质量。

---

## ClearInk 解决什么问题

阅读研究论文很少是线性的。举一个简单的例子：当一篇计算机论文中出现

```text
D(X+Y) = D(X) + D(Y) + 2Cov(X,Y)
```

它可能假定你已经知道协方差的展开式、符号约定以及证明背景。手动追溯这些前置知识可能耗费数小时的引文追踪。通用大语言模型常常凭记忆填补空白，给出看似合理实则错误的标题、年份、作者或页码。

ClearInk 将文献阅读视为一个依赖图问题：

1. 识别公式或概念中的各个组成部分，
2. 搜索引出或解释这些概念的前置论文，
3. 按依赖深度对来源进行排序，
4. 呈现一条带有可验证元数据和明确不确定性的阅读路径。

---

## 已实现的功能

ClearInk 目前提供：

- **Rich 终端界面** — 柠檬像素艺术欢迎画面、随模式变化的输入提示、spinner 反馈，通过 `rich` 库渲染 Markdown 输出。
- **双模式交互** — `/mode 1` 进入公式依赖分析模式，`/mode 2` 进入论文内容问答模式。可在任意输入提示处切换，无需重启会话。
- **交互式 CLI 工作流** — 提示输入论文标题和随模式变化的第二项输入（公式或问题），然后在同一会话中支持追问。
- **提示词装配式学术 agent** — 从 `data/system_prompts/base.md`、`guidelines.md`、可用技能、记忆和运行时环境动态构建系统提示词。
- **Google Scholar 技能** — 在需要学术搜索或引用工作时加载 `data/skills/google_scholar/SKILL.md`，内置通过 `scholar` CLI 验证元数据的硬性规则。
- **29 个已注册的工具 schema** — shell 执行、文件读取、glob 搜索、技能、记忆、待办事项、DAG 任务、后台任务、子代理、队友管理——创建、通信、协议关机——MCP 服务器连接、git worktree 管理和 cron 作业。
- **MCP 学术搜索** — 连接 ModelScope 和 Semantic Scholar / Crossref MCP 服务器，进行经过验证的论文搜索、元数据检索和主题发现。
- **Step 分步输出模式** — ``/step`` 启用分步回答；``/next`` 继续下一步，``/end`` 开启新一轮，``/nostep`` 关闭。两种模式均支持。
- **队友系统** — 四步协议通信（请求/响应匹配与类型安全）、空闲轮询与自主任务认领、git worktree 隔离实现并行文件操作。
- **阅读钩子 + 审计日志** — 检测引用相关提示、注入引用验证提醒、追踪已访问的论文类文件，写入本地 ``data/logs/reading-journal.md``，并记录所有系统事件到 ``data/logs/audit.jsonl``。
- **持久化记忆** — 将项目、用户、反馈、参考和知识记忆以带 YAML frontmatter 的 Markdown 文件形式存储。
- **上下文压缩** — 修剪中间轮次对话、归档大型工具输出、用占位符替换过大的消息体，并为长会话生成摘要。
- **错误恢复** — 重试瞬时 API 错误、通过压缩应对上下文溢出、为截断输出扩展 `max_tokens`。

---

## 架构

```text
                           clearink CLI
                                |
                     Rich 终端交互界面
                  user/ (console, interface, mode)
                                |
                     论文标题 + 输入提示
                                |
                      系统提示词装配
        base.md + guidelines.md + skills + memories + env
                                |
               +----------------+----------------+
               |                |                |
          钩子 (Hook)       记忆 (Memory)    错误恢复 (Error)
          14 个钩子点        frontmatter MD    retry/overflow/truncation
               |                |                |
               +----------------+----------------+
                                |
                          Agent 循环
                                |
        +-----------+-----------+-----------+-----------+
        |           |           |           |           |
    工具注册表    技能       子代理       队友        调度器
    @register   SKILL.md   delegate   team/       cron
        |
  +-----+-----+-----+-----+-----+-----+
  |     |     |     |     |     |     |
 bash  file  glob  task  todo memory ...
                                |
             上下文压缩 (Context Compaction) L1-L4
        trim / placeholder / archive / summarize
```

---

## 学术工作流与模式

ClearInk 以两种模式运行，可在任意提示处通过 `/mode 1` 或 `/mode 2` 切换：

### Mode 1 — 公式依赖分析（默认）

- **公式分解** — agent 将公式拆解为符号、运算符、定理引用以及所依赖的背景知识。
- **前置排序** — 推荐按依赖深度组织：直接依赖、背景论文和基础参考文献。
- **引用验证** — 书目元数据必须在展示前通过 Google Scholar 的 BibTeX 输出获得。
- **证据感知标注** — 章节、段落和公式引用仅在能检索到支持证据时给出。
- **不确定性自律** — 缺失的元数据或无法获取的章节证据应如实说明，而非推断。

Mode 1 输入示例：

```text
Mode 1 · Formula Analysis  (/mode 2 to switch)

Paper title: Attention Is All You Need
Formula number or description: scaled dot-product attention, Attention(Q,K,V) = softmax(QK^T / sqrt(d_k))V
```

### Mode 2 — 论文内容问答

- **先给简要回答** — agent 在列出论文之前，先用 2-4 句话简洁地回答用户的问题。
- **前置阅读推荐** — 随后推荐有助于深入理解该主题的论文，并附带章节级标注。
- 同样的引用验证和反幻觉规则适用。

Mode 2 输入示例：

```text
Mode 2 · Paper Q&A  (/mode 1 to switch)

Paper title: BERT: Pre-training of Deep Bidirectional Transformers
Your question about the paper: 为什么 BERT 将层归一化放在注意力子层之前而不是之后？
```

---

## 运行时特性

| 组件 | 作用 | 可复用于 |
|-----------|------|-------------|
| `@register_tool` | 基于装饰器的工具注册，支持 JSON Schema 风格的工具定义 | 可扩展的 agent 工具系统 |
| `SKILL.md` 加载器 | 从 `data/skills/*/SKILL.md` frontmatter 动态发现技能 | 无需修改代码即可扩展领域行为 |
| 子代理委托 | Flash 模型子代理，禁用 thinking，最多 5 个工具回合 | 低成本的并行查找或文件读取任务 |
| 队友系统 | 后台线程 + 协议通信 + 空闲轮询 + 自主任务认领 + git worktree 隔离 | 多 agent 研究工作流 |
| MCP 客户端 | Stdio JSON-RPC 客户端；连接外部工具服务器并动态注册其工具 | 学术搜索（ModelScope、Semantic Scholar、Crossref） |
| DAG 任务系统 | 依赖解析的任务图，支持 claim/complete/unblock 流程 | 研究规划和工作流追踪 |
| 上下文压缩 | L1-L4 四层压缩，适用于长对话 | 在 token 限制下的长会话管理 |
| 错误恢复 | 重试、上下文溢出恢复和截断重试处理 | 更可靠的 API 调用 |
| 钩子系统 | 14 个钩子点，覆盖会话、模式、MCP、队友、任务和 API 生命周期事件 + 内置 JSONL 审计日志 | 日志记录、策略提醒、阅读上下文和系统审计 |
| 持久化记忆 | Markdown + YAML frontmatter 记忆存储 | 用户偏好和项目知识 |
| Cron 调度器 | 5 字段 cron 作业，持久化到 JSON | 定期重复的研究提示 |

---

## 快速开始

### 前置条件

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- 一个 Anthropic 兼容的 API key 和端点
- 可选但建议用于引用验证：`scholar` CLI 在 `PATH` 中可用

### 安装

```bash
git clone https://github.com/Mr-remon219/ClearInk.git
cd ClearInk
uv sync
```

### 配置

从模板创建 `data/environment/.env`：

```bash
cp data/environment/.env.sample data/environment/.env
```

然后编辑 `.env` 填入你实际的 key 和端点：

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://api.anthropic.com
MODEL=claude-opus-4-1-20250805

# DeepSeek 兼容端点示例：
# ANTHROPIC_BASE_URL=https://api.deepseek.example
# MODEL=deepseek-v4-pro

# 可选：thinking 控制
THINKING_TYPE=enabled
THINKING_BUDGET=4096

# 可选：DeepSeek 兼容的 effort 字段（仅 DeepSeek 端点会转发）
THINKING_EFFORT=max

# 可选：用于子代理和队友的更廉价模型
SUBAGENT_MODEL=deepseek-v4-flash
```

运行时状态默认写入 `data/`。如果以打包形式或 Django 后端方式部署，建议在启动前通过进程环境变量设置 `CLEARINK_DATA_DIR`，把 `.env`、日志、记忆、任务、MCP 配置和队友 mailbox 都收束到一个明确目录。
如果 Django 进程不是从要被 ClearInk 管理的 Git 仓库目录启动，还应设置 `CLEARINK_REPO_ROOT` 指向该仓库路径，确保 worktree 操作作用于预期仓库。

如果你使用 Google Scholar 技能，还需确保 `scholar` 已安装并认证：

```bash
command -v scholar
scholar auth
```

### 运行

```bash
uv run clearink
```

CLI 会先展示一个柠檬像素艺术欢迎画面，显示当前模式，然后提示输入：

```text
  Mode 1 · Formula Analysis  (/mode 2 to switch)

Paper title: Attention Is All You Need
Formula number or description: scaled dot-product attention formula

  Analyzing...
```

在收到第一个回答后，可以继续追问以深入探讨、通过 `/mode 1` 或 `/mode 2` 切换模式，或使用 `/exit` 退出。

---

## 项目结构

```text
ClearInk/
├── pyproject.toml
├── README.md
├── README_zh.md
├── LICENSE
├── data/
│   ├── environment/.env        运行时 API 配置，不纳入版本控制
│   ├── skills/
│   │   └── google_scholar/
│   │       └── SKILL.md
│   ├── system_prompts/
│   │   ├── base.md
│   │   ├── guidelines.md
│   │   ├── mode1.md            Mode 1 指令（公式依赖分析）
│   │   ├── mode2.md            Mode 2 指令（论文内容问答）
│   │   └── .memory/            运行时记忆文件
│   ├── .tasks/                 运行时 DAG 任务持久化
│   ├── .scheduled_tasks/       运行时 cron 持久化
│   ├── .transcripts/           运行时压缩归档
│   ├── team/                   运行时队友消息总线
│   └── task_outputs/           归档的大型工具输出
└── src/clearink/
    ├── main.py                 入口点和 agent 循环
    ├── config.py
    ├── api/                    Django 友好的纯 Python API 桥接层
    ├── context_compact/        L1-L4 压缩
    ├── error_recovery/         重试、溢出、截断
    ├── hook/                   可插拔钩子、阅读钩子、审计日志
    ├── message/                内容块序列化与文本提取
    ├── system_prompt/          提示词装配与记忆
    ├── tool/                   已注册的工具（各自独立子包）
    │   ├── basetool/           bash、文件、glob
    │   ├── background/         后台任务执行
    │   ├── mcp_client/         MCP stdio JSON-RPC 客户端
    │   ├── scheduler/          cron 任务调度
    │   ├── skill/              SKILL.md 加载器
    │   ├── subagent/           同步子代理委托
    │   ├── task_system/        DAG 任务管理
    │   ├── team/               队友系统（协议、空闲、worktree）
    │   └── todo/               扁平 TODO 列表
    └── user/                   Rich CLI 交互界面
        ├── console.py          控制台主题与柠檬像素艺术
        ├── interface.py        交互式提示循环
        ├── mode.py             模式状态、step 模式与命令检测
        └── output_format.py    LaTeX 到纯文本转换
```

部分 `data/` 子目录在运行时自动创建，在刚克隆的仓库中可能不存在。

---

## 扩展 ClearInk

### 添加工具

```python
from clearink.tool.register import register_tool


@register_tool(
    name="arxiv_search",
    description="按关键词搜索 ArXiv 并返回论文元数据",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
        },
        "required": ["query"],
    },
)
def arxiv_search(query: str) -> str:
    return f"Results for: {query}"
```

从 `clearink.tool.__init__` 或其他已导入的模块中导入此模块，以便装饰器在启动时执行。

### 添加技能

创建 `data/skills/zotero/SKILL.md`：

```markdown
---
name: zotero
description: 通过 zotero-cli 工具查询和管理本地 Zotero 文献库
---

# Zotero 技能

使用 `zotero` CLI 来搜索、导出和管理引用……
```

技能在运行时自动被发现，并通过 `load_skill` 暴露给 agent。

### 添加钩子

```python
from clearink.hook.hook import register_hook


@register_hook("posttooluse", name="log_tools", priority=50)
def log_tool_usage(context):
    print(f"[{context.get('tool_name')}] -> {str(context.get('result'))[:100]}")
```

有效的钩子点：``userpromptsubmit``、``pretooluse``、``posttooluse``、``stop``、``session_created``、``session_destroyed``、``mode_switched``、``step_mode_changed``、``mcp_connected``、``mcp_disconnected``、``teammate_spawned``、``teammate_stopped``、``task_lifecycle``、``api_request``。

---

## 当前局限

- 公式分解由 LLM 引导，目前还没有确定性的公式解析器。
- 章节、段落和公式标注需要有可获取的原文或可靠的检索证据支持。
- Google Scholar 工作流依赖外部的 `scholar` CLI 及其认证状态。
- `run_bash` 当前使用 `shell=True`；如需在多用户环境中使用，请先做好沙箱隔离。
- 测试覆盖核心输出格式、DeepSeek 兼容请求参数、API 会话流程、钩子、MCP 注册、调度器行为、worktree 辅助逻辑和集成流程。
- 部分多 agent 工具仍属实验性质，在生产环境中使用前需要更多覆盖。

---

## 路线图

- [ ] `run_bash` 的沙箱化命令执行
- [x] 对核心输出格式和 thinking replay 行为的单元测试
- [x] 使用 mock Anthropic 兼容 API 调用的集成测试
- [ ] Lint、类型检查和测试的 CI
- [x] ArXiv、Semantic Scholar 论文搜索（MCP 集成）
- [ ] Zotero 和 PDF 文本提取技能
- [ ] 更强的章节级标注证据追踪
- [ ] 浏览器端 Web 界面
- [ ] PyPI 发布工作流

---

## 开发

```bash
uv sync
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run clearink
```

欢迎在 alpha 阶段参与贡献：

1. Fork 本仓库。
2. 创建一个功能分支。
3. 保持改动聚焦，运行 `uv run --no-sync pytest` 和 `uv run --no-sync ruff check .`。
4. 提交一个带有行为和风险简要说明的 pull request。

Issues 和讨论在 [GitHub](https://github.com/Mr-remon219/ClearInk) 上跟踪。

---

## 许可证

MIT License。详见 [LICENSE](LICENSE)。

Copyright (c) 2026 柠檬山上的柠檬精

---

*清砚 — clear ink. 每个公式被清晰拆解，每条前置知识被追溯呈现，每条通往理解的道路变得清晰可见。*
