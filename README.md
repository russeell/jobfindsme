# JobFindsMe

> **厌倦了在不同招聘 App 之间来回切换？让岗位来找你。**

**把你已经在用的 AI Agent 变成求职引擎。说一句话，JobFindsMe 同时搜索百度、腾讯、字节跳动、美团、滴滴、哔哩哔哩等 7 个企业官网，根据你的简历自动匹配，告诉你为什么合适，给你投递链接。**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![Release](https://img.shields.io/github/v/release/russeell/jobfindsme?include_prereleases)](https://github.com/russeell/jobfindsme/releases)
[![License](https://img.shields.io/github/license/russeell/jobfindsme)](LICENSE)

> 当前版本 **v0.2.0-rc.4** — 7 个自动 Connector + 22 个直达搜索链接，143 项自动化测试，支持 ZCode / Codex / Claude Code / Qwen Code。

---

## 一句话

**不是你去追岗位，是岗位来找你。** JobFindsMe 同时搜索 7 个企业官网，匹配你的简历，告诉你为什么合适——在一个 Agent 对话里完成。

> 核心理念：**让用户以最快的速度，从最多的高质量来源中，找到真正匹配的岗位。** 不追求花哨功能，只追求「搜得全、匹配准、投得快」。

```text
你（在 ZCode / Codex / Claude Code 中）：
  "用 JobFindsMe，根据我的简历，
   找上海和杭州的 AI 应用工程师岗位，期望 20-40K，0-3 年"

Agent + JobFindsMe：
  1. 本地解析简历 → 自动确认技能事实
  2. 从百度/腾讯/Airbnb 公开 API 拉取岗位
  3. 硬过滤（地点/薪资/年限/排除词）→ 去重 → 证据匹配
  4. 返回 Top 10 + 匹配理由 + 投递链接
  5. 同时给出 28 个官网直达搜索入口
```

---

## 覆盖中国主要招聘渠道

### 官网自动抓取（7 家，Agent 直接拉取）

企业以官网为主要招聘渠道的，建立自动 Connector：

| 来源 | 技术 |
|------|------|
| 百度、腾讯 | SSR / JSON-LD 解析 |
| 字节跳动、美团、滴滴、哔哩哔哩 | Playwright SPA 渲染 |
| Airbnb 中国 | Greenhouse 公开 API |

### 招聘平台（覆盖 90% 中国企业，开发中）

大多数中国企业不靠官网招人，而是靠 BOSS直聘和猎聘。
接入这两个平台 = 一次性覆盖几乎所有中国公司的岗位。

| 平台 | 覆盖 | 接入方案 |
|------|------|---------|
| BOSS直聘 | 几乎所有中国公司 | 用户授权浏览器桥 🔜 |
| 猎聘 | 中高端岗位 | 用户授权浏览器桥 🔜 |

### 直达搜索链接（29 家，一键打开）

无法自动接入的官网，提供动态搜索链接：

| 分类 | 企业 |
|------|------|
| 互联网 | 阿里巴巴、华为、京东、网易、拼多多、小红书、快手、小米、携程、蚂蚁集团、联想 |
| AI & 新势力 | 科大讯飞、旷视科技、商汤科技、知乎、蔚来、理想汽车、小鹏汽车、大疆、米哈游 |
| 招聘平台 | BOSS直聘、猎聘、智联招聘、前程无忧 |

---

## 为什么不用招聘 App？

| | 招聘 App | JobFindsMe |
|---|---|---|
| 简历 | 上传到平台 | **留在本地**，只保留结构化事实 |
| 推荐 | 黑盒算法，不知为什么推荐 | **每条匹配都有证据**：你的哪项技能匹配 JD 的哪条要求 |
| 跨平台 | 逐个 App 搜索 | **一个入口搜 28 个来源** |
| API 依赖 | 无 | 已有 Agent 直接用，**不用额外配置模型 API** |
| 数据导出 | 通常不支持 | **一键导出**，完整删除有双重确认 |

---

## 快速开始

### 1. 安装

需要 Python 3.11+。

```bash
python3 -m pip install \
  "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.4"
jobfindsme doctor
```

### 2. 接入你的 Agent

```bash
jobfindsme install zcode    # ZCode（推荐）
jobfindsme install codex    # Codex
jobfindsme install claude   # Claude Code
jobfindsme install qwen     # Qwen Code
```

重启 Agent，然后说：

```
用 JobFindsMe，根据 ~/Documents/resume.pdf，
找上海和杭州的 AI 应用工程师岗位，0-3 年经验。
```

不需要提供 Workspace ID、Search Plan ID 或任何内部参数 — Core 自动处理。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 🔒 **本地优先** | 简历解析、搜索方案、岗位状态全部存本地 SQLite |
| 🤖 **Agent 原生** | 不造新聊天界面，直接嵌入你已经在用的 AI Agent |
| 🔗 **28 个来源** | 3 个自动发现 + 25 个直达官网/平台链接 |
| 📊 **证据匹配** | 每条推荐都有简历证据 → JD 证据的对照 |
| 📌 **状态追踪** | 收藏 / 忽略 / 已投递，支持状态历史 |
| 🔄 **持续监控** | 定时刷新来源，推送新增匹配岗位（可选飞书通知） |
| 📤 **数据自由** | 一键导出、两阶段安全删除 |
| ✅ **无 API Key 也能用** | 确定性 Core 不依赖外部模型 |

---

## 工作原理

```
你的 Agent（ZCode / Codex / Claude Code）
        │
        ▼
  JobFindsMe MCP Server（本地 stdio）
        │
        ▼
  确定性 Core
  ├── 简历解析 → 结构化事实
  ├── 岗位发现 → 百度/腾讯/Airbnb API + 28 个直达链接
  ├── 过滤去重 → 硬条件 + 岗位指纹
  ├── 证据匹配 → BM25 + 关键词 + 技能对照
  ├── 状态管理 → 收藏/忽略/已投递
  └── 本地 SQLite
```

**职责边界**：Agent 负责理解和交互，Core 负责事实、状态与执行。

---

## MCP 工具

| 工具 | 用途 |
|------|------|
| `setup_profile` | 导入简历，自动确认事实 |
| `configure_search` | 配置搜索条件（角色/城市/薪资/年限） |
| `search_jobs` | 发现岗位 + 执行匹配 |
| `get_jobs` | 分页读取岗位摘要 |
| `get_job_details` | 查看单个岗位详情 |
| `update_job_state` | 收藏 / 忽略 / 标记已投递 |
| `configure_monitor` | 配置定时监控 |
| `export_local_data` | 导出本地数据 |
| `delete_local_data` | 两阶段安全删除 |

---

## 隐私与安全

- 简历路径交给 JobFindsMe，Agent **不读取完整简历**
- 默认只保存结构化事实和最少证据，不长期保存原始简历
- JD 是不可信外部内容，默认只返回有限摘要
- 删除强制执行「预览 + 短期确认令牌」两步协议
- HTTP 请求逐跳检查重定向，拒绝本地/私网/带凭据 URL

---

## 当前状态

`v0.2.0-rc.4`：

- ✅ 143 个自动化测试，Python 3.11 / 3.12 CI
- ✅ 4 个 Agent 集成（ZCode / Codex / Claude Code / Qwen Code）
- ✅ 3 个自动 Connector + 28 个官方直达链接
- ✅ 安装 / 升级 / 卸载 / 诊断一键完成
- ✅ 中文岗位匹配与证据解释
- 🔜 真实中文岗位标注基准（进行中）
- 🔜 个人实地试用报告（进行中）

---

## 参与贡献

最有价值的贡献是让 JobFindsMe 在真实求职中更可靠：

- 提交脱敏的错排/漏排/重复/失效岗位 Bad Case
- 增加稳定且合规的企业招聘官网 Connector
- 补充中文职位别名、地点、薪资和年限样本
- 改进 Agent Skill、安装兼容性和隐私边界

请先通过 [Issue](https://github.com/russeell/jobfindsme/issues) 讨论。

## 免责声明

- JobFindsMe 是一个本地工具，帮助用户整理和匹配**用户自己有权访问**的岗位信息。
- BOSS直聘 Connector 通过 Chrome DevTools Protocol 连接**用户自己的浏览器**，在用户已登录的会话中调用搜索接口。JobFindsMe 不保存、不传输、不接触用户的 BOSS 账号密码或 Cookie。
- 使用本工具产生的任何后果（包括但不限于平台账号限制）由使用者自行承担。
- 本项目仅供个人求职使用，禁止用于商业转售、大规模爬取或对目标平台造成负担的行为。

## License

[MIT](LICENSE)
