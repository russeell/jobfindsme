# jobfindsme Product And Architecture Specification

> Status: active development
>
> Baseline: Outcome-first, Multi-source, Incremental job discovery
>
> Updated: 2026-07-30

## 1. Product Goal

jobfindsme 面向技术求职者和 AI 工具用户。它不是新的招聘网站，也不是每次返回
一批相似结果的一次性搜索器，而是一个可由现有 AI Agent 调用的多来源职位发现与
推荐引擎。

系统的首要任务是用最少操作和时间，从多个来源找到更多有效、匹配且不重复的岗位。
本地画像、搜索计划、岗位身份、版本和用户状态用于支撑这个结果，而不是产品定位本身。
首次搜索建立岗位基线；后续搜索优先报告新增、变化和此前遗漏的高匹配岗位。

一句话定位：

> 一个入口搜索多个招聘来源，自动去重、筛选和解释；以后只看真正值得关注的新机会。

### 1.1 Product Promise

jobfindsme 必须同时回答四个用户问题：

1. **覆盖是否足够？** 衡量有效、匹配且唯一的岗位，而不是 Connector 或抓取数量。
2. **是否节省时间？** 减少平台切换、重复搜索和阅读无关 JD 的时间。
3. **推荐是否准确？** Top 结果符合硬条件，并提供可核查的简历与 JD 证据。
4. **操作是否简单？** 首次用一句自然语言完成配置和搜索，后续不重复配置。

### 1.2 North-star Metric And Guardrails

北极星指标：

> 每个活跃 Search Plan 每周发现并展示的、此前未见且真正值得用户打开的合格岗位数。

该指标必须结合人工相关性、岗位有效性和用户行为解释，不能由系统自己生成标签后自证。

| 目标 | 核心指标 |
|---|---|
| 有效覆盖 | Qualified Unique Jobs@10、非主来源合格岗位增量、有效投递链接率 |
| 节省时间 | 首次有效结果耗时、每日查看耗时、避免重复展示数量 |
| 推荐质量 | Precision@10、NDCG@10、硬过滤误杀率、用户收藏/忽略反馈 |
| 操作简单 | 首次完成步骤数、需要用户回答的轮数、零内部 ID 暴露率、任务完成率 |
| 持续价值 | 每周新增合格岗位数、7 日复用率、岗位变化发现率、重复结果抑制率 |

原始 `discovered` 数量、配置的来源数量和合成数据准确率不能单独作为产品效果声明。

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
- persistent job states and monitor baselines for incremental discovery;
- zero-ID first use with automatic Workspace and Search Plan;
- prompt templates covering all search dimensions.
- a profile-derived Search Plan proposal that uses confirmed facts only,
  exposes uncertainty, and requires user confirmation before persistence;

V0.2 explicitly excludes:

- unbounded browser crawlers or a large catalog of unverified company connectors;
- a public Web application, accounts, cloud database, or multi-tenancy;
- automatic applications or bypassing login and anti-bot controls;
- a custom agent runtime;
- mandatory model APIs, vector databases, Redis, or hosted queues.

The next product increment must complete:

- canonical jobs across sources instead of treating each source URL as a new job;
- first-search baseline and novelty-aware subsequent results;
- changed, reopened, and closed job detection;
- source-neutral ranking with evidence confidence;
- detail enrichment for high-value candidates from list-only sources;
- cross-source human evaluation rather than a BOSS-only Top 10.
- a hybrid source layer that prefers structured HTTP/API connectors and starts
  or attaches to a browser only for sources that genuinely require it.

### 2.1 Incremental search contract

Every successful search is scoped to one Workspace and Search Plan. The Core,
not the host Agent, persists which canonical jobs were actually shown. A later
search classifies qualified jobs as `new`, `changed`, `reopened`, or
`unchanged`; closed jobs appear in the changes summary instead of occupying a
recommendation slot.

The default response suppresses unchanged and rejected jobs. An explicit
`include_seen=true` request returns historical qualified jobs, including their
current saved or applied state. Search diagnostics distinguish a true
no-qualified-delta result from source failure and an empty local cache.

## 3. Product Principles

1. Job truth and liveness come before match scores.
2. Agent handles understanding and interaction; Core handles facts, state, and execution.
3. Every adapter calls the same Core and contains no business rules.
4. No API key means the complete deterministic workflow still works.
5. Resume content stays local and is minimized after parsing.
6. Source transport follows API/HTTP first, authenticated browser session second,
   and DOM extraction last; a browser bridge is not a universal dependency.
7. Security cannot depend on a host agent or MCP client's optional behavior.
8. Repeated searches must produce useful deltas, not repeat the same result list.
9. A source is supported only after it passes live quality gates; configured is not verified.

## 4. Main User Flow

```text
Install → jobfindsme config → paste JSON → restart agent
         (or: agent reads INSTALL.md and auto-installs)

First use:
  → agent checks whether the dedicated browser bridge is running
  → if no: jobfindsme setup → scan BOSS QR → keep bridge running

First search:
  → agent passes resume path to setup_profile
  → configure_search with roles, cities, salary, etc.
  → discover from currently healthy sources
  → normalize and deduplicate into canonical jobs
  → return the first high-confidence baseline with evidence and apply links
  → user saves / dismisses / marks applied

Later searches:
  → reuse the same Search Plan and prior job baseline
  → refresh healthy sources
  → compare canonical jobs and versions
  → exclude unchanged jobs already shown or rejected
  → report new, changed, reopened, and closed jobs

No qualified delta:
  → say that no new high-quality job was found
  → do not fill the answer with old or weakly related results
```

### 4.1 User Experience Contract

- 首次输入只要求本地简历路径和自然语言求职目标；只有影响搜索结果的关键歧义才追问。
- 默认最多进行一次集中确认，不逐项询问每个可选条件。
- 普通用户永远不需要提供 Workspace ID、Plan ID、Connector 类型或平台内部参数。
- 后续“继续帮我找”必须复用已确认画像、计划和历史状态，不重新导入简历或创建计划。
- 交互式搜索优先尽快返回合格结果；慢来源失败时不得阻塞全部结果，并必须展示来源状态。
- 结果只展示达到资格门槛的岗位，不为了数量填充无关或已看结果。
- 每条推荐必须包含岗位事实、匹配证据、主要差距、变化状态和直接投递链接。
- 用户反馈的收藏、已投和不感兴趣必须进入后续检索与排序，但不能偷偷改变硬条件。

### 4.2 Retention Contract

使用黏性来自持续减少用户工作量，而不是增加通知或强迫打开：

```text
首次搜索建立基线
  -> 用户查看 / 收藏 / 已投 / 不感兴趣
  -> Core 保存明确反馈
  -> 后续搜索抑制重复并报告高价值变化
  -> 真实 Bad Case 回流评测和工程改进
```

通知默认关闭，必须由用户主动启用；没有合格新增时应明确告知“暂无值得推荐的新岗位”，
不得用低质量旧结果制造活跃感。

## 5. Architecture

```text
Any MCP Agent (Claude Code / Codex / ZCode / Hermes / …)
        │
        ▼
    AGENTS.md (read once, universal instructions)
        │
        ▼
  jobfindsme MCP Server (local stdio adapter)
        │
        ▼
  JobFindsMe Core
        ├── Search Plan + Candidate Profile
        ├── Source Scheduler + Connector Health
        ├── Multi-source Discovery
        ├── Normalization + Canonical Job Deduplication
        ├── Candidate Detail Enrichment
        ├── Hard Filters + Evidence-based Ranking
        ├── Job Versions + Seen/Saved/Applied/Rejected State
        └── Novelty and Change Detection
        │
        ▼
  First run: ranked baseline
  Later runs: new / changed / reopened / closed digest
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
|- CanonicalJobs and SourceRecords
|- MatchEvidence
|- FeedbackEvents and JobState
|- MonitorRuns and JobStateEvents
`- SearchCursors and SourceHealth
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
search_jobs         — refresh + matching; first run creates a result baseline
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

### 10.1 来源能力必须分级

| 等级 | 含义 | 是否进入默认推荐 |
|---|---|---|
| `verified` | 实时抓取、关键字段、链接和人工相关性评测均达标 | 是 |
| `discovery` | 能发现列表岗位，但详情或分类字段不完整 | 仅作候选发现 |
| `degraded` | 验证码、限流、页面变化或连续零结果 | 使用缓存或跳过 |
| `experimental` | Connector 已实现但尚无稳定现场证据 | 否 |

当前已经接入 BOSS直聘、猎聘、前程无忧、智联和拉勾的本地浏览器 Connector，
但不同来源的数据完整度和稳定性不同。文档不得把“已经接入”表述成“已经提供
同等质量推荐”。来源只有通过 Live Loop 和人工标注后才能升级为 `verified`。

### 10.2 技术方案

当前平台 Connector 主要通过 Chrome CDP 实现：
- **BOSS直聘**：注入 XHR 调用内部搜索 API（明文薪资）
- **猎聘 / 智联**：导航搜索页 → JS DOM 提取 → 对最多 3 个候选做有界详情补全
- **前程无忧**：导航搜索页 → JS DOM 提取；详情依赖 SPA 弹窗，当前仅保留列表证据
- **拉勾**：导航搜索页 → JS DOM 提取；可能触发滑动验证，当前属于实验性来源

任何列表卡片都必须标记为 `list_card`，不能伪装成完整 JD。详情补全成功后才可
标记为 `detail_page`，并记录详情 URL 与抓取时间；结构化 API/ATS 直接提供完整描述时
标记为 `structured_source`。详情补全是尽力而为的增强步骤，失败不得阻断其他来源或
把空描述提升为完整候选。

用户运行 `jobfindsme setup` 启动隔离 Chrome profile，并登录 BOSS。
搜索期间浏览器桥必须运行。其他平台通常不要求账号，但可能触发验证或临时限制。

这不是目标架构。每个来源必须选择最低成本且可审查的传输方式：

| 优先级 | 方式 | 适用场景 |
|---|---|---|
| 1 | 官方或公开结构化 API / ATS feed | 腾讯、美团、阿里、Greenhouse、Lever 等可直接返回岗位结构 |
| 2 | 无登录 HTTP 列表与详情端点 | 页面背后有稳定公开请求，且个人低频访问符合项目边界 |
| 3 | 已登录浏览器会话中的受控请求 | BOSS 等确实依赖用户登录态的来源 |
| 4 | CDP DOM 提取 | 没有稳定结构化端点、必须执行 JavaScript 的兜底来源 |
| 5 | URL / CSV / JSON 导入 | 来源不可自动访问或用户主动提供数据 |

采用混合架构的原因：

- HTTP/API 请求比页面导航更快，字段通常更完整，也不会弹出大量标签页；
- 列表发现与详情增强可以分开，避免为每个候选岗位打开页面；
- 只有需要登录态的来源才要求浏览器桥，降低安装和首次使用成本；
- 每种 Connector 仍必须遵守限速、超时、来源条款和现场质量门禁。

不得直接复制第三方项目中绕过风控、批量抓取或关闭 robots 约束的实现。公开接口
仍可能变化或受服务条款限制，因此每个 API Connector 都必须有域名白名单、Fixture、
契约测试、限速、失败降级和 dated Live Loop 证据。

交互式搜索与全量采集必须分离，来源调度同时考虑实时产出、字段完整度、
历史成功率、延迟和验证码状态：

| 模式 | 远程行为 | 适用场景 |
|------|----------|----------|
| `fast`（默认） | 仅刷新当前城市的 BOSS，其他平台复用本地缓存 | 用户正在对话并等待结果 |
| `cache` | 不访问远程来源 | 继续比较、排序或查看已发现岗位 |
| `full` | 刷新已配置的全部平台和城市 | 定时监控、Live Loop、用户明确要求全量刷新 |

该设计借鉴 RFC 5861 的 stale-while-revalidate / stale-if-error 思想：低延迟路径可使用
可见的新鲜度状态与缓存结果，慢速刷新独立执行；缓存不得伪装成实时结果。多城市必须分别
建立来源查询，不能只取第一个城市。

### 10.3 已移除实现与重新引入条件

以下旧实现已从默认源移除，但“旧实现无效”不代表对应来源类型永远无效：

| 旧实现 | 移除原因 | 重新引入条件 |
|---|---|---|
| Playwright SPA | 浏览器成本高、字段质量和稳定性不足 | 替换成有测试的结构化 API，或证明浏览器是唯一可行方式 |
| BaiduCareer SSR | 单次验证没有产生目标岗位 | 能提供可复现的中国目标岗位增量 |
| Greenhouse / Ashby / Lever 样例 | 选定公司样例没有产生足够中国目标岗位 | 作为通用 ATS Connector，通过多公司中国岗位验证 |
| JsonLdCareerSite | 没有实际来源使用 | 至少一个稳定官网和真实回归 Fixture |

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

首次搜索按分数降序返回基线。后续搜索默认输出增量摘要：

1. 新发现的高匹配岗位；
2. 已收藏岗位的重要变化；
3. 重新开放或已经关闭的岗位；
4. 本轮过滤的重复、已看过和低相关岗位数量。

低于门槛的结果自动过滤，但门槛必须由人工评测确定。系统不得为了凑满数量重复展示
旧结果或插入低相关岗位。匹配分表示确定性排序分，不得宣传为录用概率。
固定文本输出由 Core Presentation 生成，不依赖宿主 Agent 自行读取结构化字段后发挥；
`search_jobs` 同时返回刷新模式、端到端耗时和逐来源状态。

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
| 来源实现 | [Career-Ops providers](https://github.com/santifer/career-ops/tree/main/providers)、[JobSpy](https://github.com/speedyapply/JobSpy)、[mcp-jobs](https://github.com/mergedao/mcp-jobs) | API/HTTP 优先、并发来源请求、列表与详情分离、浏览器作为必要兜底 | 不采用每次抓取都启动浏览器、无状态重复结果或未经验证的批量访问 |
| 官方工程指南 | [Anthropic Agent Evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)、[LangSmith Evaluation](https://docs.langchain.com/langsmith/evaluation-concepts)、[Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml) | Eval-driven development、线上问题回流离线数据集、生产与评测使用同一数据路径 | 不引入必须联网的托管评测平台 |
| 论文与 Benchmark | [RAGAS](https://arxiv.org/abs/2309.15217)、[ARES](https://arxiv.org/abs/2311.09476) | 分组件指标、少量人工标注校准自动评测 | 不用单个总分代替来源、数据、排序和用户价值指标 |

从 `M24-001` 起，`scripts/check_feature.py` 会自动要求 Feature 声明研究门禁，
并校验上述类别、采用/拒绝理由和本地约束；遗漏开关本身也无法生成通过证据。

### 12.2 三层评测面

| 评测面 | 主要指标 | 负责模块 | 能回答的问题 |
|---|---|---|---|
| Runtime / Source | 来源成功率、超时率、P50/P95、零结果率、缓存降级率 | Connector、浏览器桥、运行时 | 能否稳定、及时取得真实岗位 |
| Data Truth | 必填字段完整率、未知分类率、重复率、链接有效率、来源越界 | Parser、Normalizer、Canonical Job、Liveness | 岗位数据是否真实、完整、可投递 |
| Recommendation / User | Precision@10、NDCG@10、Qualified Unique Jobs@10、非主来源增量、首次有效结果耗时、每日查看耗时、避免重复数量、打开/收藏/投递 | Matcher、Search Plan、Novelty、Agent 工作流 | 推荐是否真的值得用户花时间并持续使用 |
| Operation / UX | 首次步骤数、用户确认轮数、内部参数暴露率、端到端任务成功率 | Agent Skill、MCP Adapter、Core 默认上下文 | 用户能否用一句话完成首次搜索并低成本复用 |

来源或字段质量未达到门槛时，不允许通过调整排序权重掩盖问题。合成数据只用于回归，
不能证明真实中文岗位推荐质量；自动评分不能替代用户相关性和链接有效性的人工标注。

### 12.3 快速评测漏斗

连续 7 天不是日常迭代门禁。它只能验证来源随时间波动、增量岗位发现和用户复用，
不能替代快速回归，也不应让一个明确的 Bug 等待 7 天才能修复。评测按成本逐层升级：

| 层级 | 目标 | 输入与方法 | 期望耗时 | 失败后的动作 |
|---|---|---|---:|---|
| L0 契约门禁 | 发现确定性错误 | 单元、Schema、解析 Fixture、安全和格式测试 | 1–2 分钟 | 直接阻止提交 |
| L1 快照回放 | 发现历史能力退化 | 保存的真实列表/详情快照、Golden Bad Case、时间快照对 | 2–5 分钟 | 定位到 Connector/Parser/Matcher |
| L2 单次 Live Smoke | 验证当前来源与延迟 | 一次真实搜索，记录来源状态、字段完整度、去重和端到端时间 | 5–15 分钟 | 立即生成工程建议，不等待多日 |
| L3 快速人工比较 | 判断推荐是否更好 | 对同一候选集盲测 baseline 与 candidate Top 10，标注更优/相同/更差及原因 | 15–30 分钟 | 失败样本进入 Bad Case；明显退化立即停止 |
| L4 时间行为验证 | 验证不重复和变化发现 | 两个真实快照或带时间戳的回放，检查 new/changed/reopened/closed | 当天可完成 | 修复身份、版本或增量逻辑 |
| L5 发布/声明证据 | 验证稳健性和公开指标 | 3 次以上独立真实运行、50+ 人工标签、保留留出集 | 1–3 天可累计 | 不发布指标或降级来源 |
| L6 可选耐久研究 | 观察长期波动和复用 | 7 天或更长的自然使用 | 不阻塞普通 Feature | 用于稳定版、留存和监控策略 |

采用漏斗的原因是先用便宜的必要条件淘汰失败方案，只让少量候选进入昂贵的人工与
真实来源评测。L2 的一次运行足以产生反馈，但不足以发布“稳定、准确”声明；L5 才是
公开质量门禁。相同页面、缓存或环境故障导致的多次运行不视为独立证据。

### 12.4 快速反馈与改进循环

```text
代码或配置变更
  -> L0 契约测试
  -> L1 历史快照 + Bad Case 回放
  -> 与当前 main 做逐岗位成对比较
  -> L2 单次真实来源影子运行
  -> 人工只标注差异最大的 Top 10
  -> 自动按 Source / Data / Filter / Rank / UX 归因
  -> 生成 Engineering Improvement Proposal
  -> 人工审批 Spec / Feature
  -> 失败样本加入开发集并写确定性回归
  -> 保留集确认没有过拟合
  -> 再跑一次真实影子搜索
  -> 合并、回滚或升级到 L5
```

优先采用**成对比较**而不是反复给绝对分：对同一批岗位同时展示 baseline 和 candidate，
让标注者判断哪一版排序更有用，并记录胜负原因。只标注发生变化或模型不确定的样本，
不重复标注完全相同结果。出现来源全失败、硬条件泄漏、有效链接退化或明显 P@10 下降时
立即提前停止，不继续消耗时间。

为防止“修一道、只测一道”的过拟合，数据分为：

- `regression`：历史 Bad Case，允许开发时反复运行；
- `comparison`：本轮 baseline/candidate 差异样本，用于快速人工判断；
- `holdout`：开发过程不可见，只在准备合并或发布时运行；
- `live`：当前真实来源，只用于验证外部环境和发现新 Bad Case。

所有报告保存代码 SHA、配置 Hash、数据集版本、快照时间、来源状态和输入 Hash。自动指标
只能回答其负责的问题，不能用排序分掩盖来源缺失，也不能用单次 Live Smoke 宣传准确率。

指标到工程改动的所有权必须明确：来源成功率归 Connector；字段完整度归解析与标准化；
重复率归 canonicalization；硬过滤误杀归薪资/地点/年限/招聘类型解析；P@10 归候选资格
与过滤；NDCG@10 归排序；有效链接率归 canonical URL 与 liveness；首次有效结果耗时归
Agent 工作流和运行时。

`jobfindsme.evaluation.improvement` 从第一次 Loop 就可以输出带优先级、目标值、建议验收
条件和必需测试的快速工程提案；多次独立 Loop 与人工 benchmark 只用于提升发布证据等级。
它不得自动修改 Spec、Feature 状态或代码，最终设计决策由人审批。

```bash
python -m jobfindsme.evaluation.improvement \
  --loop-report reports/loops/day-1.json \
  --loop-report reports/loops/day-2.json \
  --benchmark reports/evaluation/chinese-benchmark.json \
  --output reports/improvements/current.json
```

数据集、阈值、配置、代码版本和输入报告 Hash 必须随结果保存。调参集与留出集分离；
Bad Case 修复后进入永久回归集；公开指标必须同时通过运行证据和人工 benchmark。
真实中文 Benchmark 还必须声明 `field_trial` provenance，并关联至少 3 份未被修改的
Live Loop 报告及 SHA256。脚本构造的岗位、链接、来源状态或标签只能作为 synthetic
regression；即使样本数和分数达标，也不得产生 `ready_for_claim=true`。

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
16. □ Canonical Job、跨来源去重和岗位版本变化检测。
17. □ 首次结果基线与后续增量摘要，默认不重复展示已看岗位。
18. □ 候选详情增强和来源质量分级。
19. □ 完成快速评测漏斗：单次 Live 反馈、成对比较、时间快照回放和独立留出集。
20. □ 稳定版前可选进行 7 天耐久研究；它不阻塞普通 Feature 修复与合并。
