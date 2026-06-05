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

**ClearInk**（清砚）是一个双模式学术阅读 agent。

**Mode 1**（默认）——你提供论文标题和看不懂的公式，ClearInk 会分解公式、通过 Google Scholar 验证引用元数据，并返回一条带有精确章节、段落或公式标注的前置阅读路径。

**Mode 2** ——你对论文内容提问，ClearInk 会先给出简短解答，再推荐用于深入理解的前置论文。

会话中可随时通过 ``/mode 1`` 或 ``/mode 2`` 切换模式。

**Step 模式**（``/step``）将回答拆分为分步输出——总体解释 → 论文路线 → 逐篇详析——你可以逐步消化，通过 ``/next`` 继续、``/end`` 结束当前轮并开启新一轮对话。

ClearInk 内置基于 Rich 的终端界面——柠檬像素艺术欢迎画面、随模式变化的输入提示、spinner 等待动画以及 Markdown 渲染输出——整体风格参考了现代开发者工具的简洁 CLI 美学。

在底层实现上，ClearInk 同时也是一套紧凑的 Python agent 运行时，包括：Anthropic 兼容的 CLI 循环、基于装饰器的工具注册、``SKILL.md`` 技能扩展、持久化记忆、钩子系统、子代理、带协议通信与 git worktree 隔离的队友系统、MCP 学术搜索客户端（ModelScope、Semantic Scholar / Crossref）、上下文压缩、错误恢复，以及便于 Django 后端接入的 API 桥接层。

项目目前处于 **alpha** 阶段。引用策略是刻意从严设计的：论文元数据必须来自 `scholar --bibtex` 或 `scholar cite`；缺失字段应如实报告为"不可用"而非猜测填充。章节级标注的精确程度取决于 agent 可检索到的证据质量。

---

## ClearInk 解决什么问题

阅读研究论文很少是线性的。举一个简单的例子：当一篇计算机论文中出现

```text
D(X+Y) = D(X) + D(Y) + 2Cov(X,Y)
```

论文可能假定你已经知道协方差的展开式、符号约定以及证明背景。要理清这些前置依赖，可能要耗费数小时的引文回溯。通用大语言模型常常凭记忆填补空白，给出看似合理实则错误的标题、年份、作者或页码。

ClearInk 将文献阅读视为一个依赖图问题：

1. 识别公式或概念中的各个组成部分，
2. 搜索引出或解释这些概念的前置论文，
3. 按依赖深度对来源进行排序，
4. 呈现一条带有可验证元数据和明确不确定性的阅读路径。

---

## 已实现的功能

### 交互

- **Rich 终端界面** — 柠檬像素艺术欢迎画面、随模式变化的输入提示、spinner 反馈，以及通过 `rich` 渲染的 Markdown 输出。
- **双模式交互** — ``/mode 1`` 进入公式依赖分析，``/mode 2`` 进入论文内容问答。可在会话中随时切换，无需重启。
- **Step 分步输出** — ``/step`` 启用分步回答；``/next`` 继续下一步，``/end`` 开启新一轮。

### 工具链

- **Google Scholar 技能** — 按需加载学术搜索能力，内置通过 `scholar` CLI 验证元数据的硬性规则。
- **MCP 学术搜索** — 连接 ModelScope、Semantic Scholar 和 Crossref，进行经过验证的论文搜索与元数据检索。
- **29 个已注册工具** — shell 执行、文件读写、glob 搜索、技能、记忆、待办事项、DAG 任务、后台任务、子代理、队友管理、MCP 客户端、git worktree 管理和 cron 作业。

### Agent 运行时

- **系统提示词装配** — 从 `data/system_prompts/` 模板、可用技能、记忆和运行时环境动态构建系统提示词。
- **队友系统** — 四阶段协议通信，支持空闲轮询、自主任务认领和 git worktree 隔离。
- **阅读钩子与审计日志** — 引用验证提醒、论文文件访问追踪和 JSONL 审计日志。
- **持久化记忆** — 以 Markdown + YAML frontmatter 存储用户偏好和项目知识。
- **上下文压缩** — L1–L4 四层压缩：修剪、占位符、归档、摘要，适用于长时间运行的会话。
- **错误恢复** — 瞬时 API 错误重试、上下文溢出处理和截断恢复。

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
          钩子系统          记忆系统          错误恢复
          14 个钩子点       frontmatter MD    retry/overflow/truncation
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
             上下文压缩 L1-L4
        trim / placeholder / archive / summarize
```

---

## 学术工作流与模式

ClearInk 以两种模式运行，可在任意提示处通过 `/mode 1` 或 `/mode 2` 切换：

### Mode 1 — 公式依赖分析（默认）

- **公式分解** — agent 将公式拆解为符号、运算符、定理引用以及前置依赖的背景知识。
- **前置排序** — 推荐按依赖深度组织：直接依赖、背景论文和基础参考文献。
- **引用验证** — 书目元数据必须在展示前通过 Google Scholar 的 BibTeX 输出获得。
- **证据感知标注** — 章节、段落和公式引用仅在能检索到支持证据时给出。
- **不确定性声明** — 缺失的元数据或无法获取的章节证据应如实报告为不可用。

Mode 1 输入示例：

```text
Mode 1 · Formula Analysis  (/mode 2 to switch)

Paper title: Attention Is All You Need
Formula number or description: scaled dot-product attention, Attention(Q,K,V) = softmax(QK^T / sqrt(d_k))V
```

### Mode 2 — 论文内容问答

- **先给简要回答** — agent 在列出论文之前，先用 2-4 句话简洁地回答用户的问题。
- **前置阅读推荐** — 随后推荐有助于深入理解该主题的论文，并附带章节级标注。
- **引用规则** — 与 Mode 1 相同的引用验证和反幻觉规则适用。

Mode 2 输入示例：

```text
Mode 2 · Paper Q&A  (/mode 1 to switch)

Paper title: BERT: Pre-training of Deep Bidirectional Transformers
Your question about the paper: 为什么 BERT 将层归一化放在注意力子层之前而不是之后？
```

---

## 运行时特性

| 组件 | 作用 | 适用场景 |
|-----------|------|-------------|
| `@register_tool` | 基于装饰器的工具注册，支持 JSON Schema 风格的工具定义 | 可扩展的 agent 工具系统 |
| `SKILL.md` 加载器 | 从 `data/skills/*/SKILL.md` frontmatter 动态发现技能 | 无需修改代码即可扩展领域行为 |
| 子代理委托 | 轻量模型子代理，禁用 thinking，最多 5 个工具回合 | 低成本的并行查找或文件读取任务 |
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

### 第一步：安装

**前置条件：** Python 3.14+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/Mr-remon219/ClearInk.git
cd ClearInk
uv sync
```

### 第二步：配置

从模板复制环境变量文件，然后填入你自己的值：

```bash
# macOS / Linux
cp data/environment/.env.sample data/environment/.env

# Windows (命令提示符)
copy data\environment\.env.sample data\environment\.env
```

用任意文本编辑器打开 `data/environment/.env`，**必须**填入以下三项：

```env
ANTHROPIC_API_KEY=<your-api-key>
ANTHROPIC_BASE_URL=<your-api-endpoint>
MODEL=<your-model-name>
```

其余变量（thinking 控制、子代理模型、路径覆盖等）均为可选，默认值与详细说明
见 `.env.sample` 文件内的注释。

### 第三步：运行

```bash
uv run clearink
```

看到柠檬像素艺术欢迎画面即说明运行成功。接下来：

```text
  Mode 1 · Formula Analysis  (/mode 2 to switch)

Paper title: Attention Is All You Need
Formula number or description: scaled dot-product attention formula

  Analyzing...
```

收到第一个回答后，可以继续追问、通过 `/mode 1` 或 `/mode 2` 切换模式，或使用
`/exit` 退出。

### 可选设置

**Google Scholar（引用验证）：**

```bash
command -v scholar
scholar auth
```

**高级 — 自定义数据路径：**
在启动前设置 `CLEARINK_DATA_DIR` 可将 `.env`、日志、记忆、任务和 MCP 配置统一
存放到指定目录。当工作目录与 ClearInk 所要管理的 Git 仓库不同时，设置
`CLEARINK_REPO_ROOT` 指向仓库路径（worktree 操作需要）。

---

## 项目结构

```text
ClearInk/
├── pyproject.toml
├── README.md
├── README_zh.md
├── LICENSE
├── data/
│   ├── environment/
│   │   ├── .env.sample          配置模板（可安全提交）
│   │   └── .env                 运行时 API 配置，不纳入版本控制
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
    ├── system_prompt/          系统提示词装配与记忆
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

部分 `data/` 子目录由运行时自动创建，首次运行前可能不存在。

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

请确保此模块在启动时被导入，以便装饰器注册生效（例如在 `clearink.tool.__init__` 中引用）。

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

- 公式分解依赖 LLM 判断，目前还没有确定性的公式解析器。
- 章节、段落和公式标注需要有可获取的原文或可靠的检索证据支持。
- Google Scholar 工作流依赖外部的 `scholar` CLI 及其认证状态。
- `run_bash` 当前使用 `shell=True`；未做沙箱隔离前请勿暴露给不受信任的用户。
- 部分多 agent 功能仍属实验性质，需要更充分的测试后再用于生产环境。

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
