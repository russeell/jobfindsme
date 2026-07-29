# jobfindsme Product And Architecture Specification

> Status: v0.2 active development
>
> Baseline: Agent-native, Local-first, MCP-standard
>
> Updated: 2026-07-29

## 1. Product Goal

jobfindsme 面向技术求职者和 AI 工具用户。提供本地简历或描述求职目标，
由 AI Agent 调用 jobfindsme，从五大招聘平台同步搜索、匹配和跟踪岗位。

一句话定位：

> 本地优先的 AI 求职引擎 — 五大平台一站式搜索，简历本地匹配，投递直达。

## 2. V0.2 Scope

V0.2 provides:

- local Workspace with accepted candidate profile;
- multiple Search Plans sharing profile facts;
- local resume parsing (auto-confirm fast path or paginated review);
- **5 CDP platform connectors** (BOSS直聘 · 猎聘 · 前程无忧 · 智联 · 拉勾);
- normalization, versioning, deduplication, freshness, and liveness checks;
- deterministic hard filters, BM25 ranking, match evidence, and **score threshold** (min 10%);
- job states (saved / applied / rejected) and feedback history;
- CLI, local stdio MCP Server, and **generic MCP install** (`jobfindsme config`);
- `AGENTS.md` — framework-agnostic Agent instructions for all MCP hosts;
- installer, upgrade, uninstall, doctor (with BOSS login check), and self-update;
- reproducible offline evaluation;
- optional local monitoring and Feishu summaries;
- zero-ID first use with automatic Workspace and Search Plan;
- prompt templates covering all search dimensions.

V0.2 explicitly excludes:

- Playwright SPA, SSR/JSON-LD, Greenhouse, Ashby, and Lever connectors (removed — redundant with platforms);
- a public Web application, accounts, cloud database, or multi-tenancy;
- automatic applications or bypassing login and anti-bot controls;
- a custom agent runtime;
- mandatory model APIs, vector databases, Redis, or hosted queues.

## 3. Product Principles

1. Job truth and liveness come before match scores.
2. Agent handles understanding and interaction; Core handles facts, state, and execution.
3. Every adapter calls the same Core and contains no business rules.
4. No API key means the complete deterministic workflow still works.
5. Resume content stays local and is minimized after parsing.
6. All maintained sources use a local CDP browser bridge; BOSS also requires account login.
7. Security cannot depend on a host agent or MCP client's optional behavior.

## 4. Main User Flow

```text
Install → jobfindsme config → paste JSON → restart agent
         (or: agent reads INSTALL.md and auto-installs)

First use:
  → agent checks whether the dedicated browser bridge is running
  → if no: jobfindsme setup → scan BOSS QR → keep bridge running

Search:
  → agent passes resume path to setup_profile
  → configure_search with roles, cities, salary, etc.
  → search_jobs across 5 platforms
  → results with match%, evidence, apply links
  → user saves / dismisses / marks applied

Results below 10% match are automatically filtered.
```

## 5. Architecture

```text
Any MCP Agent (Claude Code / Codex / ZCode / Hermes / …)
        │
        ▼
    AGENTS.md (read once, universal instructions)
        │
        ▼
  jobfindsme MCP Server (local stdio)
        │
        ├── BOSS直聘 CDP ────── 15+ jobs/query (requires login)
        ├── 猎聘 CDP ────────── 42+ jobs/query (no login)
        ├── 前程无忧 CDP ─────── 20+ jobs/query (no login)
        ├── 智联招聘 CDP ─────── 15+ jobs/query (no login)
        └── 拉勾 CDP ────────── 15+ jobs/query (no login)
        │
        ▼
    Deduplicate → Filter (≥10%) → BM25 Rank → Evidence → Top N + reasons + links
```

Core must not import FastAPI, MCP SDKs, agent SDKs, or UI packages.

## 6. Local Data Model

```text
Workspace
|- CandidateProfile
|  |- SourceDocument
|  `- ProfileFacts
|- SearchPlan A / B …
|- Jobs and JobVersions
|- MatchEvidence
|- FeedbackEvents and JobState
`- MonitorRuns and JobStateEvents
```

Profile facts are shared across plans. Role, location, salary, experience,
and exclusions belong to a Search Plan.

## 7. Resume Privacy

The agent must not read the complete resume. Pass only the file path to
`setup_profile`. Import modes: `reference`, `managed`, `forget-source`.
Default auto-confirms facts for immediate first search.

## 8. Destructive Operation Safety

Two-phase deletion: `preview` → `confirm` with short-lived single-use token.

## 9. MCP Surface

```text
setup_profile       — import and parse resume
configure_search    — set roles, cities, salary, exclusions
search_jobs         — discover across 5 platforms + match
get_jobs            — pagination and state filtering
get_job_details     — single job detail (untrusted external content)
update_job_state    — save / applied / rejected
configure_monitor   — recurring scheduled checks
export_local_data   — local export (path + hash + counts only)
delete_local_data   — two-phase deletion
```

`workspace_id` and `plan_id` are optional adapter escape hatches — Core resolves
the active context automatically.

## 10. Source Strategy

### 10.1 五个平台，覆盖主流渠道

| 平台 | 访问前提 | 特点 |
|------|------|------|
| BOSS直聘 | 浏览器桥 + 登录 | 岗位量大，常见明文薪资 |
| 猎聘 | 浏览器桥 | 中高端 + 外企中国岗 |
| 前程无忧 | 浏览器桥 | 传统行业 + IT，覆盖面广 |
| 智联招聘 | 浏览器桥 | 综合招聘 |
| 拉勾 | 浏览器桥 | 互联网岗位 |

腾讯、阿里、字节、拼多多、小米、网易、美团……绝大部分公司的岗位
都在这五个平台上发布。不保证覆盖所有公司所有岗位。

### 10.2 技术方案

全部通过 Chrome CDP 实现：
- **BOSS直聘**：注入 XHR 调用内部搜索 API（明文薪资）
- **猎聘 / 前程无忧 / 智联 / 拉勾**：导航搜索页 → JS DOM 提取

用户运行 `jobfindsme setup` 启动隔离 Chrome profile，并登录 BOSS。
搜索期间浏览器桥必须运行。其他平台通常不要求账号，但可能触发验证或临时限制。

### 10.3 删掉的 Connector

以下 Connector 已从默认源移除（冗余或零产出）：

| Connector | 原因 |
|-----------|------|
| Playwright SPA (字节/美团/滴滴/B站) | 岗位已在五大平台上 |
| BaiduCareer (SSR) | 同上 |
| Greenhouse (Airbnb) | 0 条中国 AI 岗 |
| Ashby (Airwallex) | 数据解析 bug，0 条 |
| Lever | API 大面积关闭 |
| JsonLdCareerSite | 未被任何源使用 |

代码保留 `JSON_FILE` 和 `CSV_FILE` 用于用户自导入。

### 10.4 Agent Compatibility

jobfindsme 是标准 MCP Server。适配所有 MCP 兼容的 Agent：

```text
安装方式：
  jobfindsme config           → 输出标准 JSON → 粘贴到任意 Agent 配置
  jobfindsme install --path   → 直接写入自定义配置路径
  jobfindsme install <name>   → 快捷安装（claude / codex / zcode / …）
```

`AGENTS.md` 提供框架无关的调用说明，所有 Agent 首次读取后即可使用。

### 10.5 Live Search Loop

真实抓取必须生成机器报告：来源状态与耗时、discovered/unique/version 数量、
端到端耗时、结果数量、字段完整度、未知分类和重复链接。Top 10 同时生成待人工
标注模板。自动检查不能替代相关性、链接有效性和实际投递价值的人工判断。

## 11. Output Format

每条岗位必须包含四项：

1. 岗位介绍 — title, company, location, salary, track, type
2. 匹配度 — 🎯 percentage
3. 投递链接 — 🔗 source-platform direct job URL
4. 推荐理由 — evidence-based (reasons + warnings)

低于 10% 匹配的结果自动过滤。按分数降序，最多 15 条。

## 12. Design Research and Evaluation-Driven Engineering

### 12.1 Research Gate：先研究，再设计

高风险 Feature 在进入 `ready` 前必须完成可审查的 Research Gate。研究的目的不是
复制热门项目，而是识别成熟模式、适用边界和本项目约束。最低证据组合为：

1. 一个真实生产或开源实现；
2. 一份维护者或平台官方工程指南；
3. 一篇相关论文或公开 benchmark（算法、排序、Agent、评测类设计必需）。

每条资料必须在 `feature_list.json` 中记录：

- `adopted_pattern`：本项目采用的具体设计；
- `rejected_or_not_adopted`：明确不采用或延后的部分及原因；
- `local_constraints`：中国岗位来源、本地隐私、无强制模型 API、维护成本、
  反爬和用户时间成本等约束。

不能仅以 star 数、文章结论或单次 Demo 作为设计依据。安全和数据丢失问题可先做
紧急止损，但正式发布前仍须补齐研究记录、回归测试和实测证据。历史 Feature 不做
机械补录；从启用 Research Gate 的 Feature 开始强制执行。

当前设计依据包括：

| 类型 | 参考 | 采用 | 不直接采用 |
|---|---|---|---|
| 开源项目 | [Career-Ops](https://github.com/santifer/career-ops)、[AI Job Search](https://github.com/MadsLorentzen/ai-job-search) | 本地优先、Agent 原生、结构化岗位评价、真实使用反馈 | 不复制自动投递、特定国家站点和模型强依赖 |
| 官方工程指南 | [Anthropic Agent Evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)、[LangSmith Evaluation](https://docs.langchain.com/langsmith/evaluation-concepts)、[Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml) | Eval-driven development、线上问题回流离线数据集、生产与评测使用同一数据路径 | 不引入必须联网的托管评测平台 |
| 论文与 Benchmark | [RAGAS](https://arxiv.org/abs/2309.15217)、[ARES](https://arxiv.org/abs/2311.09476) | 分组件指标、少量人工标注校准自动评测 | 不用单个总分代替来源、数据、排序和用户价值指标 |

从 `M24-001` 起，`scripts/check_feature.py` 会自动要求 Feature 声明研究门禁，
并校验上述类别、采用/拒绝理由和本地约束；遗漏开关本身也无法生成通过证据。

### 12.2 三层评测面

| 评测面 | 主要指标 | 负责模块 | 能回答的问题 |
|---|---|---|---|
| Runtime / Source | 来源成功率、超时率、P50/P95、零结果率、缓存降级率 | Connector、浏览器桥、运行时 | 能否稳定、及时取得真实岗位 |
| Data Truth | 必填字段完整率、未知分类率、重复率、链接有效率、来源越界 | Parser、Normalizer、Canonical Job、Liveness | 岗位数据是否真实、完整、可投递 |
| Recommendation / User | Precision@10、NDCG@10、硬过滤误杀率、首次有效结果耗时、打开/收藏/投递 | Matcher、Search Plan、Agent 工作流 | 推荐是否真的值得用户花时间 |

来源或字段质量未达到门槛时，不允许通过调整排序权重掩盖问题。合成数据只用于回归，
不能证明真实中文岗位推荐质量；自动评分不能替代用户相关性和链接有效性的人工标注。

### 12.3 评测驱动的工程闭环

```text
真实搜索运行
  -> Live Loop 报告
  -> Top 10 人工标注
  -> 多日聚合与根因分类
  -> Engineering Improvement Proposal
  -> 人工审批 Spec / Feature
  -> 先加入失败 fixture 或能力评测
  -> 实现修复
  -> 离线回归与留出集对比
  -> 真实来源影子复跑
  -> 发布或回滚
```

指标到工程改动的所有权必须明确：来源成功率归 Connector；字段完整度归解析与标准化；
重复率归 canonicalization；硬过滤误杀归薪资/地点/年限/招聘类型解析；P@10 归候选资格
与过滤；NDCG@10 归排序；有效链接率归 canonical URL 与 liveness；首次有效结果耗时归
Agent 工作流和运行时。

`jobfindsme.evaluation.improvement` 聚合多次 Loop 与人工 benchmark，输出带优先级、
目标值、建议验收条件和必需测试的工程提案。它不得自动修改 Spec、Feature 状态或代码；
最终设计决策由人审批。

```bash
python -m jobfindsme.evaluation.improvement \
  --loop-report reports/loops/day-1.json \
  --loop-report reports/loops/day-2.json \
  --benchmark reports/evaluation/chinese-benchmark.json \
  --output reports/improvements/current.json
```

数据集、阈值、配置、代码版本和输入报告 Hash 必须随结果保存。调参集与留出集分离；
Bad Case 修复后进入永久回归集；公开指标必须同时通过运行证据和人工 benchmark。

## 13. Delivery Milestones

1. ✅ Product and architecture baseline.
2. ✅ Local Workspace, Search Plans, and resume lifecycle.
3. ✅ Deterministic matching, offline evaluation.
4. ✅ Product-grade CLI and local stdio MCP Server.
5. ✅ Generic MCP install + AGENTS.md for all agents.
6. ✅ One-command install, upgrade, uninstall, doctor, self-update.
7. ✅ Score threshold filtering (≥10%).
8. ✅ 5 CDP platform connectors (BOSS / Liepin / 51job / Zhaopin / Lagou).
9. ✅ Prompt templates with full field coverage.
10. ✅ BOSS login tutorial with screenshot.
11. ✅ CI pipeline (ruff + pytest + smoke test).
12. □ Personal field trial with logged-in BOSS session.
13. □ Labeled benchmark (50+ jobs across multiple days).
14. □ Monitor + Feishu notifications in production.
15. □ Release hardening and PyPI publication.
