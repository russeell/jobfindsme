<div align="center">

# jobfindsme · 你的本地求职雷达

**让你的 AI Agent 持续替你找工作：跨来源发现、只看新增、记住每次选择。**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![latest](https://img.shields.io/badge/release-latest-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[为什么用它](#为什么不用招聘-app) · [快速开始](#快速开始) · [提示词模版](#提示词模版) · [FAQ](#faq) · [English](README.en.md)

<img src="docs/search-results.png" alt="jobfindsme 搜索结果" width="760" />

</div>

---

第一次，你只需说：

```text
用 jobfindsme，根据这份本地简历（路径：~/Documents/resume.pdf），
找上海和杭州的 AI 应用工程师岗位，20K以上，社招，正式。
```

jobfindsme 会在本地解析简历，并给出带依据、需要你确认的求职条件建议；确认后
再发现和匹配岗位。之后再次搜索时，
它应优先告诉你新增、变化和遗漏的高匹配岗位，而不是重新塞给你同一批结果。
这里的 `~/Documents/resume.pdf` 是用户电脑上的**简历文件路径**；Agent 应把路径
交给 jobfindsme Core 本地解析，而不是读取或复制完整简历。

<div align="center">
<img src="docs/demo.gif" alt="jobfindsme demo" width="860" />
</div>

```text
第二天：
新增 3 个高匹配岗位。
昨天展示过的 10 个岗位没有重复出现。
你收藏的一个岗位更新了技能要求。
```

> 搜索结果按 Workspace + Search Plan 记录本地展示基线。默认只返回新增、
> 内容变更和重新开放的岗位；需要回看历史结果时，让 Agent 使用
> `include_seen=true`。收藏、投递和忽略状态不会因再次搜索而重置。

## 它解决什么问题？

| 求职中的重复劳动 | jobfindsme 的目标体验 |
|---|---|---|
| 每天切换多个招聘 App | 一个 Agent 入口访问多个来源 |
| 反复看到同一个岗位 | 跨来源去重，并记住已看、收藏、投递和忽略 |
| 不知道今天有什么变化 | 后续搜索聚焦新增、变更、重开和关闭岗位 |
| 推荐理由是黑盒 | 每条岗位提供匹配分、证据、风险和投递链接 |
| 求职状态散落在不同平台 | 本地 SQLite 统一保存，随时导出和删除 |
| 不想额外配置模型 API | 确定性 Core 无 API Key 也能运行 |

## 三个产品目标

1. **找得更多**：衡量真正值得投递的不同岗位，不以抓取总数冒充覆盖率。
2. **花时更少**：减少平台切换和重复阅读，缩短从提出需求到看到好岗位的时间。
3. **推荐更准**：严格执行地点、薪资、招聘类型等条件，并给出可核对的证据。

## 什么时候不适合用它

说清楚比藏着掖着好：

- **你想海投** —— jobfindsme 不做自动投递。它帮你找到值得投的岗位，点链接自己投。
- **你要覆盖所有公司** —— 已接入的平台仍可能漏掉官网、内推或受访问限制的岗位。
- **你不方便运行本地浏览器桥** —— 当前五个平台都通过本地 Chrome CDP 读取；BOSS 还需要账号登录。
- **你期待录用概率预测** —— 当前分数是可解释的确定性排序分，不是录用概率。

## 当前能力边界

- BOSS直聘可以获取较丰富的列表字段；其他平台目前主要承担岗位发现，详情和招聘类型仍需增强。
- “接入五个平台”不等于五个平台已经具备相同的推荐质量。
- 拉勾等来源可能触发验证码；失败时系统应跳过或使用明确标注的新鲜缓存。
- 当前真实人工评测样本仍不足，不能把单日 BOSS Top 10 指标宣传成跨平台推荐准确率。
- 当前五个平台 Connector 仍依赖本地浏览器桥。目标架构将优先使用公开结构化 API/HTTP，
  仅在确实需要登录或执行 JavaScript 时使用浏览器。
- 下一阶段重点是混合来源层、候选详情增强、来源质量分级、Canonical Job 和增量结果摘要，
  而不是继续增加低质量平台数量。

## 快速开始

jobfindsme 是标准 **MCP Server**，适配所有 MCP 兼容的 Agent（Claude Code、Codex、Kimi、TRAE、WorkBuddy、ZCode、Hermes、OpenClaw、Qoder……）。

### 第 1 步：安装

最简单的方式 —— 跟你的 Agent 说一句话：

```text
帮我安装 jobfindsme：https://github.com/russeell/jobfindsme/blob/main/INSTALL.md
```

Agent 会自动装包、配置 MCP、安装 Skill。

或者手动：

```bash
pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@main"
jobfindsme install claude    # Claude Code。换成 codex / kimi / trae / zcode / workbuddy 均可
```

> [!TIP]
> Agent 不在快捷名单里？`jobfindsme config` 输出标准 MCP JSON，粘贴到任意 Agent 的配置文件即可。

### 第 2 步：启动本地浏览器桥并登录 BOSS

```bash
jobfindsme setup   # 启动隔离 Chrome；登录后搜索期间保持它运行
```

![BOSS直聘登录](docs/boss-login.png)

> [!IMPORTANT]
> 五个平台都通过这个本地浏览器桥搜索。只有 BOSS 必须登录账号；其他平台通常可直接访问，但仍可能触发验证码或临时限制。

### 第 3 步：重启 Agent，开始搜索

```text
用 jobfindsme，根据这份本地简历（路径：~/Documents/resume.pdf），
找上海和杭州的 AI 应用工程师岗位，20K以上，社招，正式。
```

## 提示词模版

直接抄改：

```bash
# 有简历，精确搜
用 jobfindsme，根据这份本地简历（路径：~/Documents/我的简历.pdf），
找上海和深圳的 AI Agent 工程师岗位，25K以上，社招，正式，1-5年经验。

# 有简历，放宽搜
用 jobfindsme，根据这份本地简历（路径：~/Documents/我的简历.pdf），
找杭州的大模型应用开发岗位，校招。

# 无简历，快速浏览
用 jobfindsme，搜北京的自动驾驶算法岗位，30K以上，社招。

# 查看详情 / 收藏
用 jobfindsme，看一下第 3 个岗位的详细内容。
用 jobfindsme，把第 1、4、6 个岗位存起来。
```

**完整字段**（`[]` 为可选，去掉不需要的行）：

```text
用 jobfindsme，
根据 [简历路径]                      ← 有简历才写，自动解析匹配
找 [城市] 的 [岗位方向] 岗位         ← 必填
薪资 [最低K]-[最高K] 或 [金额] 以上  ← 可选
[校招 / 社招]  [实习 / 正式]         ← 可选
[0-3年 / 3-5年 / …] 经验            ← 可选
排除 [外包 / 996 / …]               ← 可选
```

## 岗位来源

| 平台 | 当前角色 | 访问前提 |
|------|------|------|
| **BOSS直聘** | 已验证的主要推荐来源 | 浏览器桥 + 登录 |
| **猎聘** | 岗位发现，详情增强中 | 浏览器桥 |
| **前程无忧** | 岗位发现，详情增强中 | 浏览器桥 |
| **智联招聘** | 岗位发现，解析质量验证中 | 浏览器桥 |
| **拉勾** | 实验性来源，可能触发验证 | 浏览器桥 |

项目用 Live Loop 持续记录来源耗时、返回数量、字段完整度、有效链接和人工相关性。
只有通过现场质量门禁的来源才会被称为“已验证推荐来源”。

长期方案不是让所有来源都走浏览器。Connector 按以下顺序选择：

```text
公开结构化 API / ATS → 无登录 HTTP → 已登录浏览器请求 → DOM 提取 → 手动导入
```

浏览器桥会保留给 BOSS 等需要用户登录态的来源；能够通过公开 JSON 接口获得完整
岗位信息的企业官网和 ATS，应直接使用轻量 HTTP Connector。

## 工作原理

```text
你说一句话
      │
      ▼
  任意 MCP Agent（Claude Code / Codex / WorkBuddy / …）
      │
      ▼
  jobfindsme MCP Server（本地 stdio）
      │
      └── 快速：刷新 BOSS + 复用缓存
      └── 全量：Chrome CDP → 五大平台
      │
      ▼
  多来源发现 → 标准化 → Canonical Job 去重
      → 硬过滤 → 证据匹配 → 岗位状态与版本
      → 首次：高匹配基线
      → 后续：新增 / 变化 / 重开 / 关闭摘要
```

简历解析、匹配、打分全部在本地完成，不依赖任何模型 API 或云端服务。

## MCP 工具

| 工具 | 做什么 |
|------|--------|
| `setup_profile` | 导入简历，自动解析技能/经验/学历 |
| `configure_search` | 设角色/城市/薪资/年限/排除词 |
| `search_jobs` | 多来源发现、去重和匹配 |
| `get_jobs` | 翻页浏览本地结果 |
| `get_job_details` | 单个岗位详情 |
| `update_job_state` | 收藏 / 忽略 / 已投递 |
| `configure_monitor` | 定时刷新 |
| `export_local_data` | 本地数据导出 |
| `delete_local_data` | 预览 → 令牌确认，两阶段安全删除 |

## 隐私与安全

- **简历不出本地** —— Agent 只拿到文件路径，完整文本不进入模型上下文
- **最少存储** —— 只存结构化事实（技能、年限、学历）和最小证据片段
- **本地数据库** —— SQLite，文件权限 0600，WAL 模式
- **删除两步走** —— `preview` 预览 → 单次令牌 `confirm`，防止误删
- **岗位描述视为不可信内容** —— 不作为指令注入模型

## FAQ

**Q：搜不到 BOSS 岗位？**
先确认专用 Chrome 仍在运行，再确认 BOSS 登录态。运行 `jobfindsme setup` 重新启动浏览器桥，也可以用 `jobfindsme doctor` 诊断。

## 真实搜索质量 Loop

单元测试只证明代码契约。真实来源是否可用、数据是否完整，要用 Live Loop 记录：

```bash
python -m jobfindsme.evaluation.live_loop \
  --agent-host codex --allow-browser-sources --day 1
```

报告保存在 `~/.jobfindsme/reports/`，包含各来源成功率与耗时、抓取/去重/匹配数量、
字段完整度和待人工标注 Top 10。产品重点观察 Qualified Unique Jobs@10、
非主来源带来的合格岗位增量、避免重复展示数量和端到端耗时。只有累计真实人工标签后，
才能对外声称推荐质量。

**Q：匹配度怎么算的？**
硬过滤（地点/薪资/年限/排除词）先砍掉不合格岗位，再用 BM25 对岗位方向打分，
加上技能覆盖、标题命中、城市命中。确定性算法，可复现。当前“匹配度”是排序分，
不是录用概率；后续会同时展示数据完整度对应的证据置信度。

**Q：没有简历能用吗？**
能。有简历才出匹配分和技能对照，没简历就是纯搜索。低于 10% 匹配的结果自动过滤。

**Q：数据存在哪？会上传吗？**
`~/.jobfindsme/data/jobfindsme.db`，本地 SQLite。没有遥测，没有云同步。`export_local_data` 一键导出，`delete_local_data` 两阶段删除。

**Q：会不会导致平台账号被限制？**
工具只在你本机操作你自己登录的 Chrome，模拟正常浏览行为。但自动化访问仍可能触发平台风控——请控制搜索频率，配合 `configure_monitor` 做定时刷新（默认 24 小时一次）而不是手动高频搜索。后果自负，详见[免责声明](#免责声明)。

## 参与贡献

- **报 Bad Case**：错排 / 漏排 / 重复 / 失效岗位 —— [提 Issue](https://github.com/russeell/jobfindsme/issues)，记得脱敏
- **提功能**：先开 Issue 描述场景和方案，讨论通过后再提 PR，避免白干
- **补语料**：中文职位别名、地点、薪资样本的 PR 永远欢迎
- **加 Connector**：欢迎补充合规的企业招聘官网 Connector

## 免责声明

jobfindsme 是本地工具，仅供学习研究和个人求职使用。

**技术手段说明：** CDP 连接器通过用户已登录的本地 Chrome 浏览器提取岗位信息，
其中 BOSS直聘 的搜索依赖注入 XHR 调用平台内部 API。
这些操作可能违反招聘平台的用户协议，使用本工具可能导致你的平台账号被限制或封禁。

**隐私提示：** 搜索返回的岗位数据（含招聘者信息）会保存在本地数据库中。
请勿将数据库文件分享给他人。

**使用者承担全部责任。** 本项目不鼓励、不支持商业转售、大规模爬取、
绕过平台反爬措施、或任何违反法律法规的使用方式。

## License

[MIT](LICENSE)
