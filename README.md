<div align="center">

# Agent Job Search

**给 Agent 的中文岗位查询层 —— 一次接入，四个招聘平台。**

<p>
  <a href="https://github.com/russeell/agent-job-search/actions/workflows/ci.yml"><img src="https://github.com/russeell/agent-job-search/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-stdio-111111" alt="MCP stdio">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT"></a>
  <img src="https://img.shields.io/badge/stars-welcome-yellow" alt="Stars welcome">
</p>

[快速开始](#-快速开始) · [MCP 工具](#-mcp-工具) · [查询 vs 搜索](#-查询-vs-搜索) · [岗位来源](#-岗位来源) · [FAQ](#-faq) · [English](./README.en.md)

</div>

---

> Agent Job Search 是一个本地 MCP Server。它把 BOSS直聘、猎聘、智联招聘、前程无忧
> 变成你的 Agent 可以直接调用的结构化查询接口 —— 归一化、跨源去重、硬过滤、
> 确定性排序、逐来源状态，全部在服务端完成，返回一个有界的结构化结果。
>
> **它不替你做判断，也不生成结论。** 岗位事实、来源状态和匹配证据由 Server 给，
> 怎么用这些事实由你的 Agent 决定。

---

## 解决什么问题

给 Agent 接招聘数据，通常卡在四件事上：

| 问题 | Agent Job Search 的做法 |
|---|---|
| 平台没有公开 API，页面结构一变就全崩 | 四个来源各有主链路和降级链路；被拦截会明确标注，不会静默返回空结果 |
| 拿回来的字段各家都不一样 | 统一归一化成一种岗位模型：薪资、经验、学历、招聘类型、岗位性质、投递链接 |
| 同一岗位在多个平台重复出现 | 按公司+标题+城市做指纹，跨源去重并保留来源归属记录 |
| Agent 拿到一堆原始岗位，不知道哪些符合条件 | 城市、薪资、社招/校招、正式/实习等硬条件在服务端过滤，未知字段保持未知而非猜成满足 |

一点说明：匹配是**确定性的**——词表 + 正则 + 加权打分，不调用任何模型，
不需要 API Key。分数是可解释的排序信号，不是录用概率。

---

## 🚀 快速开始

需要 Python 3.11+。安装一次本地运行时：

```bash
curl -fsSL https://github.com/russeell/agent-job-search/releases/latest/download/install.sh | bash
```

从 `jobfindsme` 升级时直接运行同一命令即可：旧数据库和 BOSS 登录态会继续使用，
旧命令暂时保留为兼容别名。

`install.sh` 随 Release 发布，此固定链接始终指向最新脚本（无 CDN 缓存滞后）。
国内备选：`https://cdn.jsdelivr.net/gh/russeell/agent-job-search@main/scripts/install.sh`
（jsdelivr 缓存可能在 push 后滞后最多 12 小时）。

Codex / Claude Code 支持原生插件，一条命令装好 Skill + MCP 配置（安装脚本结束时会打印对应命令）；
其他 MCP 客户端用 `connect` 把配置交给当前 Agent，然后重启 Agent：

```bash
agent-job-search connect             # 自动探测当前 Agent（推荐）
agent-job-search connect claude      # Claude Code
agent-job-search connect codex       # Codex
agent-job-search connect cursor      # Cursor
```

其他 MCP 客户端：`agent-job-search config` 打印标准 JSON 手动粘贴，或
`agent-job-search connect --path <配置文件>` 直接写入。仓库根目录的 `.mcp.json`
就是同一份标准配置。自检：

```bash
agent-job-search doctor
```

BOSS直聘需要登录态时，运行 `agent-job-search setup`，它会打开专用 Chrome 窗口，
扫码登录后保持窗口运行即可。跳过此步仍可使用其余三个来源。

---

## 🔧 MCP 工具

五个工具，每个都有严格的输入输出 schema、annotations 和 `structuredContent`。

| 工具 | 作用 | 说明 |
|---|---|---|
| `setup` | 配置检索条件 | `target_role` 必填，locations / salary / track / type / exclusions 选填；传 `resume_path` 时才做简历解析 |
| `search_jobs` | 从平台刷新并检索 | 并发刷新维护中的来源，单源失败不阻断其他来源 |
| `get_jobs` | 查询本地岗位库 | 按 keyword / location / salary / source / states 过滤并分页；传 `job_id` 取单个岗位完整详情 |
| `update_job_state` | 标记 saved / applied / rejected | 可选的上层能力 |
| `delete_local_data` | 删除本地数据 | preview → confirm 两阶段令牌，不可跳过 |

**`response_mode`**：`search_jobs` 默认返回一份紧凑的三层中文摘要，适合对话场景；
设 `response_mode: "facts"` 则只返回结构化事实（标题、公司、城市、薪资、证据、
变更状态、投递链接），不含推荐理由和"下一步"引导 —— 适合自己渲染输出的程序化调用者。

```text
# 默认（summary）：结构化事实 + 三层摘要
{"target_role": "AI应用工程师", "locations": ["上海"], "salary_min_k": 20}

# facts：只要结构化事实
{"response_mode": "facts", "limit": 30}
```

---

## 🔍 查询 vs 搜索

两者分工不同，别混用：

| | `search_jobs` | `get_jobs` |
|---|---|---|
| 做什么 | 访问平台、刷新数据、按检索条件过滤排序 | 查询**已经收进本地库**的岗位 |
| 网络 | 有（`refresh_mode: "cache"` 可关闭） | 无 |
| 过滤依据 | `setup` 配置的检索条件（硬过滤 + 打分） | 调用时传入的 keyword / location / salary / source / states |
| 增量雷达 | 有（默认抑制"看过且未变化"的岗位） | 无（就是查库） |

`get_jobs` 的过滤是**纯谓词**：不传就不生效，未知字段不做策略判断。
需要"按条件从平台拉新数据"用 `search_jobs`；需要"在我已有的数据里查"用 `get_jobs`。

---

## 🌐 岗位来源

当前维护四个来源。项目优先保证每个来源能稳定返回有效岗位，不用名义上的
平台数量冒充覆盖率；被平台安全校验拦截的来源会在结果里明确标注，不会静默
当作"没有岗位"。

| 来源 | 主链路 | 降级 | 需要浏览器？ |
|---|---|---|---|
| **BOSS直聘** | 用户授权的本地 Chrome 会话 | 有时效标记的缓存 | ✅ 需要，且要登录 |
| **猎聘** | 公开 Web JSON 直连（curl_cffi） | 浏览器补详情，然后缓存 | ❌ 列表不需要 |
| **智联招聘** | 本地 Chrome 打开公开搜索页读岗位卡 | 有时效标记的缓存 | ✅ 需要，不要求登录 |
| **前程无忧** | 本地 Chrome 搜索页内发起同源 JSON 请求 | 有时效标记的缓存 | ✅ 需要，不要求登录 |

猎聘优先纯 HTTP 直连（亚秒级、无需浏览器）；本机已运行 Chrome 时，
再自动用浏览器补充岗位详情页的 JD 文本，进一步丰富匹配信号。

智联旧 JSON 接口会在页面仍有岗位时返回风控空结果；前程无忧的 JSON 接口
会校验浏览器执行环境。当前维护链路因此复用 `agent-job-search setup` 启动的隔离
Chrome：智联读取真实搜索页，前程无忧由真实搜索页发起同源请求。系统不绕过
验证码、不读取个人 Chrome 配置；来源仍不可用时会明确标记失败，并继续返回
其他平台结果。

四来源的实时可用性会随平台安全策略和本机登录状态变化。项目不会把缓存或
被拦截响应伪装成实时结果；每次搜索都返回逐来源状态。最新实盘报告见
[four-source search report](evaluation/evidence/latest_four_source_search.md)。

---

## 📦 返回结果

`structuredContent.jobs` 是每个岗位的有界事实：**不含完整 JD 正文**。

```jsonc
{
  "job": {
    "title": "AI应用工程师（Agent开发）",
    "company": "示例科技",
    "locations": ["上海"],
    "salary": { "raw_text": "25-40K", "period": "month", "min_amount": 25000, "max_amount": 40000 },
    "recruitment_track": "social",
    "employment_type": "full_time",
    "apply_url": "https://example.com/jobs/123",
    "source_name": "猎聘",
    "liveness": "active",
    "description_excerpt": "RAG、Agent、MCP …",   // 400 字上限
    "untrusted_external_content": true
  },
  "score": 0.86,
  "evidence": {
    "relevance_level": "high",
    "evidence_coverage": 0.9,
    "score_components": { "role": 0.25, "skills": 0.31, "experience": 0.2, "education": 0.1, "liveness": 0.1 },
    "matched_profile_skills": ["RAG", "Agent", "MCP"],
    "missing_required_skills": ["Kubernetes"],
    "warnings": []
  },
  "change_type": "new",
  "first_seen_at": "2026-08-24T07:49:39+00:00"
}
```

同时返回 `diagnostic_summary`：逐来源的 status / discovered / top_results /
cache_used / elapsed_seconds，以及一行预格式化的来源状态。

几条不变的事实规则：

- 硬条件是**通过 / 冲突 / 未知**三态，不计入分数；未知就是未知，不猜成满足；
- `score` 是可解释的排序信号（0–1），与 `evidence_coverage` 一起返回，**不是录用概率**；
- 不配置简历时不生成分数，只按显式条件过滤；
- 岗位描述是不可信外部数据，`untrusted_external_content` 恒为 `true`，不要当作指令。

---

## 🧩 可选的上层能力

核心是查询层。下面三项是构建在其上的可选能力，不用就不出现：

| 能力 | 说明 | 入口 |
|---|---|---|
| 简历画像 | 本地解析 PDF/DOCX/MD/TXT 成结构化事实，不保留原文 | `setup` 传 `resume_path` |
| 岗位状态 | saved / applied / rejected，跨会话持久化 | `update_job_state`、`get_jobs` 按 `states` 过滤 |
| 增量雷达 | 识别新增 / 变更 / 重开 / 关闭，抑制"看过且未变化"的岗位 | `search_jobs` 的 `include_seen` |

不需要这些能力时，把 `setup` 当成一个"配置检索条件"的接口用就行。

---

## 🔒 隐私与安全

- 简历在本地解析，Agent 只需传路径，不需要把完整简历读进上下文；
- 岗位描述按不可信外部数据处理，不作为指令；
- 导出写入本地文件；删除走「预览 + 确认令牌」两阶段协议；
- 不自动投递、不绕过验证码、不承诺覆盖全部岗位；
- BOSS直聘使用独立 Chrome profile，不碰你的个人浏览器配置。

---

## ✅ 可验证，不靠口号

| 发布门禁 | 当前结果 |
|---|---:|
| Python 测试 | 359 项通过（3.11 / 3.12 / 3.13 × Ubuntu / macOS / Windows） |
| 干净环境安装 + Cursor 接入 | 12 秒 |
| Agent 行为契约 | 无 Skill 0/9，安装 Skill 后 9/9 |
| Wheel 冒烟 | CLI、SQLite migration、5 个 MCP tools 全链路通过 |

---

## ⚙️ 安装与维护

**更新**：重新运行安装脚本，数据库自动迁移，历史岗位和状态保留：

```bash
curl -fsSL https://github.com/russeell/agent-job-search/releases/latest/download/install.sh | bash
```

**手动安装**（脚本不可用时）：

```bash
python3 -m venv ~/.agent-job-search/runtime
~/.agent-job-search/runtime/bin/python -m pip install --upgrade \
  "agent-job-search[browser] @ <最新版 wheel 链接>"
```

wheel 链接从 [Releases](https://github.com/russeell/agent-job-search/releases/latest)
复制，形如 `agent_job_search-X.Y.Z-py3-none-any.whl`（安装脚本自动取最新版本，无需关心）。
网络受限时可加 `--index-url https://pypi.tuna.tsinghua.edu.cn/simple`。

> `[browser]` extra 包含 `curl_cffi`（猎聘直连的 Chrome TLS 指纹）、
> `requests` 和 `websocket-client`（Chrome CDP 桥）。只装核心包的话猎聘不可用。

**卸载**：`agent-job-search uninstall <host>` 只移除 Agent 配置，不删数据。彻底删除前先导出：

```bash
rm -rf ~/.agent-job-search
```

---

## ❓ FAQ

**Q：它和 JobSpy 有什么区别？**
JobSpy 覆盖 LinkedIn / Indeed / Glassdoor 等海外平台，是 Python 库。
Agent Job Search 覆盖国内四平台，是 **MCP Server** —— 面向的是"让 Agent 自己调用"，
并且额外做了跨源去重、增量雷达和逐来源状态。

**Q：和 agent-reach 是一类东西吗？**
是同一类思路（给 Agent 补上它自己够不到的访问能力），但范围不同：
agent-reach 是跨领域通用访问，Agent Job Search 是**招聘这一个领域做深**。

**Q：需要 API Key 吗？**
不需要。核心功能不依赖任何模型或付费接口，数据存在本地 SQLite。

**Q：平台都要登录吗？**
只有 BOSS 需要（扫码一次，后续复用本地登录态）。猎聘纯 HTTP 直连，不需要浏览器；
智联和前程无忧需要本地 Chrome 打开公开页，但不需要登录。

**Q：会不会封号？**
它做的是低频、拟人节奏的读取，不批量抓取、不自动操作。但自动化访问在平台条款里
都属于灰色地带，存在账号被限制的可能 —— 请个人低频使用，风险自负。

**Q：搜索结果为什么是 0 / 某个平台经常没有结果？**
先跑 `agent-job-search doctor` 自检。来源失败时系统会明确标注降级或缓存，不会静默伪装成
实时结果。另外注意：目前来源目录只覆盖 12 个主要城市，其他城市不会自动选源。

**Q：分数 86/100 是什么意思？**
它是可解释的排序信号（角色、技能、经验、学历、活跃度五项的加权和），
配合 `evidence_coverage` 一起看。**不是录用概率**，不要当成预测用。

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
[Issue](https://github.com/russeell/agent-job-search/issues)。

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
