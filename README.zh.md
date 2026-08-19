<div align="center">

# jobfindsme · AI 求职雷达

**一句话聚合 BOSS直聘、猎聘、智联招聘和前程无忧，按简历筛选并持续追踪岗位。**

<p>
  <a href="https://github.com/russeell/jobfindsme/actions/workflows/ci.yml"><img src="https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-stdio-111111" alt="MCP stdio">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT"></a>
  <img src="https://img.shields.io/badge/stars-welcome-yellow" alt="Stars welcome">
</p>

[快速开始](#-快速开始) · [怎么用](#-怎么用) · [返回结果](#-返回结果) · [岗位来源](#-岗位来源) · [FAQ](#-faq) · [English](./README.md)

</div>

---

> 给 Claude Code、Codex、Cursor 等 Agent 装一个本地求职 MCP Server。
> 它负责搜岗位、去重、排序和记住状态；Agent 负责和你聊天。

---

## 解决什么问题

每天找工作最烦的不是“不会搜索”，而是这些重复劳动：

| 问题 | jobfindsme 的做法 |
|---|---|
| 多个平台来回切 | 统一检索四个来源；单源失败会明确提示并返回其他来源 |
| 推荐一堆不相关岗位 | 先硬过滤角色、城市、薪资、社招/校招、正式/实习，再排序 |
| 反复看到同一个岗位 | 本地记录已看、已投、已忽略，只汇报变化 |
| 不知道为什么推荐 | 每个岗位固定给出匹配度、证据、风险和投递链接 |
| 不想配置模型 API | 核心功能不依赖 API Key，数据存在本地 SQLite |

一句话开始：

```text
用 jobfindsme，根据本地简历（路径：~/Documents/resume.pdf），
找上海的 AI 应用工程师，20K以上，社招，正式。
```

---

## 🚀 快速开始

### 方式一：直接和 Agent 说（推荐）

在 Claude Code、Codex、Cursor 里直接说（复制整段）：

```text
按 https://github.com/russeell/jobfindsme 的 README 安装 jobfindsme
```

Agent 会读取仓库 README 完成：安装本地运行时（
`curl -fsSL https://github.com/russeell/jobfindsme/releases/latest/download/install.sh | bash`）
→ 写入 MCP 配置（`jobfindsme connect <当前Agent>`）→ 提示重启。
首次安装需要几分钟；如果 Agent 无法访问网络，改用下面的手动方式。
`install.sh` 随 Release 发布，此固定链接始终指向最新脚本（无 CDN 缓存滞后）。
国内备选：`https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh`
（jsdelivr 缓存可能在 push 后滞后最多 12 小时）。

装好后，直接说需求即可：

```text
根据本地简历 ~/Documents/resume.pdf 找上海的 AI 应用工程师岗位，20K 以上，社招。
```

### 方式二：手动安装（1 分钟）

需要 Python 3.11+。安装一次本地运行时：

```bash
curl -fsSL https://github.com/russeell/jobfindsme/releases/latest/download/install.sh | bash
```

Codex / Claude Code 支持原生插件，一条命令装好 Skill + MCP 配置（安装脚本结束时会打印对应命令）；
其他 MCP 客户端用 `connect` 把配置交给当前 Agent，然后重启 Agent：

```bash
jobfindsme connect             # 自动探测当前 Agent（推荐）
jobfindsme connect claude      # Claude Code
jobfindsme connect codex       # Codex
jobfindsme connect cursor      # Cursor
```

其他 MCP 客户端：`jobfindsme config` 打印标准 JSON 手动粘贴，或
`jobfindsme connect --path <配置文件>` 直接写入。仓库根目录的 `.mcp.json`
就是同一份标准配置。

自检并开始：

```bash
jobfindsme doctor
```

```text
用 jobfindsme，根据 ~/Documents/resume.pdf 找上海的 AI 应用工程师，20K以上，社招。
```

完整简历由本地 Core 解析。Agent 只应把路径传给 `setup`，不得先读取全文。

BOSS直聘需要登录态时，对 Agent 说：

```text
帮我登录 BOSS直聘
```

它会打开专用 Chrome 窗口。扫码登录后保持窗口运行即可。跳过此步仍可使用无需登录的来源。

---

## ✨ 能力

| 能力 | 说明 |
|---|---|
| 一句话找岗位 | Agent 调用本地 MCP Server，自动配置搜索并返回结果 |
| 四平台来源 | BOSS直聘、猎聘、智联招聘、前程无忧；失败会明确标注 |
| 简历匹配 | 本地解析 PDF/MD/TXT，按技能、经验、学历等信号排序 |
| 事实驱动输出 | Server 返回有界结构化事实 + 五段事实摘要，Agent 组织最终表达 |
| 增量追踪 | 识别新增、变更、重开、关闭，避免重复推荐 |
| 状态记忆 | 支持保存、已投递、忽略；下次自动跳过 |
| 本地优先 | 不需要模型 API Key；简历和状态保存在本地 SQLite |

### 可验证，不靠口号

| 发布门禁 | 当前结果 |
|---|---:|
| Python 测试 | 310 项通过 |
| 干净环境安装 + Cursor 接入 | 12 秒 |
| Agent 行为契约 | 无 Skill 0/6，安装 Skill 后 6/6 |
| Wheel 冒烟 | CLI、SQLite migration、5 个 MCP tools 全链路通过 |

四来源的实时可用性会随平台安全策略和本机登录状态变化。项目不会把缓存或
被拦截响应伪装成实时结果；每次搜索都返回逐来源状态。最新实盘报告见
[four-source search report](evaluation/evidence/latest_four_source_search.md)。

---

## 💬 怎么用

直接复制改参数：

```text
# 找岗位
用 jobfindsme 根据 ~/Documents/resume.pdf 找北京的 大模型应用工程师，30K以上，社招。

# 定时推送
每天早上 9 点推送新岗位给我。

# 查历史
我之前看过的岗位有哪些？
我投过哪些岗位？

# 只看新增
继续帮我找新岗位，只要今天新增的。

# 换条件
把城市换成深圳，薪资下限改成 25K，重新搜。

# 管理状态
把刚才第 2 个岗位标记为已投递；把外包公司全部忽略。
```

---

## 📦 返回结果

Server 决定事实、过滤、排序与证据；Agent 基于返回事实组织最终回答。
每次结果包含有界结构化事实（`structuredContent.jobs`）和五段事实摘要
（简历解析 / 检索概览 / 过滤说明 / 岗位列表 / 说明），摘要可调整措辞但不得与事实矛盾：

```text
AI应用工程师（Agent开发）｜示例科技｜上海｜社招｜正式｜25-40K
匹配度：92%（信号匹配，非录用概率）
技能：RAG、Agent、MCP ｜ 经验：1-3年 ｜ 学历：本科

投递链接：https://example.com/jobs/123

推荐理由：简历技能命中：RAG、Agent、MCP；综合匹配度为 92%；薪资信息明确。
需要注意：JD 要求 Kubernetes，简历中未找到直接证据
```

岗位块固定包含：**事实行 + 匹配度 + 空行 + 投递链接（裸 URL 可点击）+ 空行 + 推荐理由**。
匹配度 = 60% 硬条件底分 + 最高 40% 信号加成（技能 > 经验 > 学历 > 活跃度 > 薪资可见），
所有能展示的岗位都已在 60%–100% 区间内，且按匹配度从高到低排列。
事实、匹配度、链接、基础推荐理由和风险都由 Server 确定生成，任何 Agent 一致；
Agent 基于返回的结构化事实组织回答，不得编造岗位、薪资、链接或分数；
用户明确要求比较或查看详情时，同一轮也可以调用 `get_jobs`。

结果不足时 Agent 不会用弱匹配岗位凑数；来源字段不完整时会明确标注。
设置薪资下限时，默认排除薪资未公开岗位；也可明确说“保留薪资面议岗位”，
系统会保留并逐条提示信息缺口。

---

## 🌐 岗位来源

当前维护四个来源：**BOSS直聘 + 猎聘 + 智联招聘 + 前程无忧**。项目优先
保证每个来源能稳定返回有效岗位，不用名义上的平台数量冒充覆盖率；被平台
安全校验拦截的来源会在结果里明确标注，不会静默当作"没有岗位"。

| 来源 | 方式 | 速度 | 需要浏览器？ |
|---|---|---|---|
| **BOSS直聘** | 用户授权的本地 Chrome 会话；失败时使用有时效标记的缓存 | 取决于登录态 | ✅ 需要 |
| **猎聘** | 公开 Web JSON 列表；浏览器可用时有界补全详情 | 通常亚秒级 | ❌ 列表不需要 |
| **智联招聘** | HTTP 优先；安全校验触发后尝试本地浏览器 | 实验性 | 仅兜底时 |
| **前程无忧** | HTTP 优先；WAF 触发后尝试本地浏览器 | 实验性 | 仅兜底时 |

猎聘优先纯 HTTP 直连（亚秒级、无需浏览器）；本机已运行 Chrome 时，
再自动用浏览器补充岗位详情页的 JD 文本，进一步丰富匹配信号。

> **智联招聘 / 前程无忧为实验性来源**：纯 HTTP 请求在部分网络环境下会被
> 安全校验拦截。系统会尝试用户授权的本地浏览器；仍不可用时明确标记失败，
> 并继续返回其他来源结果。来源数量不等于稳定覆盖率，请以本次检索概览为准。

---

## ⚙️ 工作原理

```text
Agent (Claude/GPT/Qwen/WorkBuddy — 负责交互与后续解释)
  → MCP Server (本地 stdio)
  → 本地 Core
      → 纯 HTTP 直连（猎聘 / 智联 / 前程无忧）
      → 本地 Chrome CDP（BOSS直聘登录页面上下文中执行请求）
      → live 模式：有界并行刷新全部来源，单源失败不阻断其他来源
  → 标准化 → 跨来源去重 → 硬过滤（城市/薪资/校招社招/实习正式）
  → 信号提取 + 加权粗筛（技能/经验/学历/活跃度/薪资）
  → 增量雷达（新增/变化/重开/关闭识别）
  → Server 返回有界事实 + 五段摘要；Agent 基于事实组织回答
    （不得编造事实或丢失投递链接）
```

MCP Server 负责硬过滤、结构化信号提取、确定性排序和事实基线。
Agent 负责自然语言表达；用户追问岗位对比时，才基于返回证据补充分析，
不编造事实、不丢失或改写投递链接。

简历、岗位状态和搜索计划全部保存在本地 SQLite。Core 不需要模型 API。

---

## 🔒 隐私与安全

- 完整简历不进入 Agent 上下文，只把本地路径交给 Core 解析；
- 岗位描述按不可信外部数据处理，不作为 Agent 指令；
- 导出写入本地文件；删除走「预览 + 确认令牌」两阶段协议；
- 不自动投递、不绕过验证码、不承诺覆盖全部岗位。

---

## 🔧 安装与维护

**更新**：重新运行安装脚本，数据库自动迁移，历史岗位和状态保留：

```bash
curl -fsSL https://github.com/russeell/jobfindsme/releases/latest/download/install.sh | bash
```

**手动安装**（脚本不可用时）：

```bash
python3 -m venv ~/.jobfindsme/runtime
~/.jobfindsme/runtime/bin/python -m pip install --upgrade \
  "jobfindsme[browser] @ <最新版 wheel 链接>"
```

wheel 链接从 [Releases](https://github.com/russeell/jobfindsme/releases/latest)
复制，形如 `jobfindsme-X.Y.Z-py3-none-any.whl`（安装脚本自动取最新版本，无需关心）。
网络受限时可加 `--index-url https://pypi.tuna.tsinghua.edu.cn/simple`。

**卸载**：`jobfindsme uninstall <host>` 只移除 Agent 配置，不删数据。彻底删除前先导出：

```bash
rm -rf ~/.jobfindsme
```

---

## ❓ FAQ

**Q：平台都要登录吗？**
只有 BOSS 需要（扫码一次，后续复用本地登录态）。猎聘纯 HTTP 直连，不需要浏览器。

**Q：会不会封号？**
它做的是低频、拟人节奏的读取，不批量抓取、不自动操作。但自动化访问在平台条款里
都属于灰色地带，存在账号被限制的可能 — 请个人低频使用，风险自负。

**Q：搜索结果为什么是 0 / 某个平台经常没有结果？**
先跑 `jobfindsme doctor` 自检。BOSS 检查本地 Chrome 和登录态；猎聘检查 HTTP
来源状态。来源失败时系统会明确标注降级或缓存，不会静默伪装成实时结果。

**Q：简历会被上传吗？**
不会。简历只在本地解析成结构化事实存入 SQLite，完整简历文本不进入 Agent 上下文。
`jobfindsme export` / `delete_local_data` 可随时导出和清除。

**Q：和直接把简历发给 AI 让它搜，有什么区别？**
通用 Agent 没有平台接入、没有跨天去重和状态记忆、也不能稳定解析 PDF 简历成结构化
事实。jobfindsme 把这三件事做成了确定性的本地服务，Agent 只负责对话。

**Q：安装超过 5 分钟？**
停止当前命令，保留最后输出并提交 Issue。不要让 Agent 克隆仓库、安装测试依赖或下载
整套浏览器来尝试修复。

---

## 🛠 开发

```bash
python -m pip install -e ".[dev]"
python -m pytest
ruff check . && ruff format --check .
```

架构、来源门禁和评测闭环见 [architecture](docs/architecture.md)、
[connectors](docs/connectors.md)、[evaluation](docs/evaluation.md)；
完整工程规范在 `docs/internal/project_spec.md`。
发现错排、漏排、重复或失效链接，请提交脱敏
[Issue](https://github.com/russeell/jobfindsme/issues)。

---

## ⚖️ 免责声明

- 本项目为免费开源的个人学习工具，帮助整理你**已登录、有权查看**的岗位信息；
- 自动化访问招聘平台可能触发对方风控，由此产生的账号限制、封禁等后果由使用者
  自行承担，与作者无关；
- 禁止用于商业转售、大规模爬取或绕过平台限制；
- 平台页面结构随时可能变化导致某个来源失效，请通过 Issue 反馈，作者会尽力跟进。

---

## 📄 License

[MIT](LICENSE)
