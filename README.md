<div align="center">

# jobfindsme · 你的 AI 求职雷达

**一次搜索多个招聘平台，根据简历筛出更适合你的岗位。下次只看新机会。**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![latest](https://img.shields.io/badge/release-latest-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[快速开始](#快速开始) · [它能帮你什么](#它能帮你什么) · [岗位来源](#岗位来源) · [FAQ](#faq) · [English](README.en.md)

<img src="docs/search-results.png" alt="jobfindsme 搜索结果" width="760" />

</div>

---

第一次，你只需说：

```text
用 jobfindsme，根据这份本地简历（路径：~/Documents/resume.pdf），
找上海和杭州的 AI 应用工程师岗位，20K以上，社招，正式。
```

`~/Documents/resume.pdf` 是你电脑上的简历路径。jobfindsme 在本地解析简历，
自动搜索、去重和筛选岗位，并直接给出推荐理由与投递链接。

<div align="center">
<img src="docs/demo.gif" alt="jobfindsme demo" width="860" />
</div>

第二天只需说：

```text
继续帮我找新岗位。
```

jobfindsme 会记住你的条件，以及哪些岗位已经看过、收藏或投递，只返回值得关注的
新增和变化，不再重复塞给你同一批链接。

## 它能帮你什么

- **少切平台**：一个 Agent 入口搜索多个招聘来源。
- **少看垃圾结果**：自动去重，并过滤城市、薪资、经验和招聘类型不符合的岗位。
- **更容易判断要不要投**：每条岗位给出匹配分、推荐理由、主要差距和直接链接。
- **每天只看变化**：记住已看、收藏、忽略和已投岗位，后续聚焦新机会。

结果示例：

```text
大模型应用开发工程师｜示例科技｜上海｜25-40K｜社招·正式
匹配度：86%
适合你：RAG、Agent、FastAPI 与你的项目经历匹配
需要注意：岗位要求 Kubernetes，简历中暂未找到直接证据
投递：https://example.com/jobs/123
```

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
| **BOSS直聘** | 当前主要推荐来源 | 需要登录 |
| **猎聘** | 可搜索，部分岗位可获取完整介绍 | 通常无需登录 |
| **前程无忧** | 可搜索，部分岗位信息可能不完整 | 通常无需登录 |
| **智联招聘** | 可搜索，部分岗位可获取完整介绍 | 通常无需登录 |
| **拉勾** | 试验性支持，可能触发验证 | 视页面状态而定 |

不同平台的稳定性和岗位完整度会有差异。某个来源暂时不可用时，jobfindsme 会跳过并
说明情况，不会让它拖住全部搜索。具体实现与质量标准见 [PROJECT_SPEC.md](PROJECT_SPEC.md)。

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

开发原则、来源质量门禁和评测闭环见 [PROJECT_SPEC.md](PROJECT_SPEC.md)。

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
