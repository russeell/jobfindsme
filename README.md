# JobFindsMe · AI 求职引擎

> **5 大平台一站式搜索 · 本地简历智能匹配 · 投递链接直达**
>
> BOSS直聘 · 猎聘 · 前程无忧 · 智联招聘 · 拉勾

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![v0.2.0-rc.5](https://img.shields.io/badge/release-v0.2.0--rc.5-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**JobFindsMe** 是一个标准 MCP Server，让你的 AI Agent（ZCode、Claude Code、Codex 等）变成求职引擎。接入五大招聘平台，一句话搜索，本地简历匹配，每条结果都有匹配度、推荐理由和直达投递链接。

- 🔍 **一站式搜索** — 同时搜 BOSS直聘、猎聘、前程无忧、智联、拉勾
- 📄 **本地简历匹配** — 简历不出本地，AI 自动解析技能/经验/学历
- 📊 **每条有证据** — 匹配度百分比 + 技能对照 + 推荐理由
- 🔗 **投递链接直达** — 点击即跳转官方岗位页
- 🔌 **标准 MCP** — 适用所有 MCP 兼容 Agent，无需逐个适配

---

## 快速开始

JobFindsMe 是一个标准 **MCP Server**，适配所有 MCP 兼容的 Agent（ZCode、Claude Code、Codex、Kimi、TRAE、Qoder、Hermes、OpenClaw……）。

### 1. 安装

```bash
pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.5"
```

### 2. 配置 MCP

**方式 A：输出 JSON 自己粘贴（推荐，适用所有 Agent）**

```bash
jobfindsme config
```

输出类似：

```json
{
  "mcpServers": {
    "jobfindsme": {
      "command": "/path/to/python",
      "args": ["-m", "jobfindsme.mcp"]
    }
  }
}
```

粘贴到任意 Agent 的 MCP 配置文件，或用 `--path` 直接写入：

```bash
jobfindsme install --path ~/.your-agent/mcp.json
```

**方式 B：快捷安装（已知 Agent）**

```bash
jobfindsme install zcode     # ZCode
jobfindsme install claude    # Claude Code
jobfindsme install codex     # Codex
jobfindsme install kimi      # Kimi Code
jobfindsme install trae      # TRAE
# ... 其他 Agent 用方式 A
```

**方式 C：让 Agent 帮你装**

```
帮我安装 JobFindsMe：https://github.com/russeell/jobfindsme/blob/main/INSTALL.md
```

### 3. 重启 Agent，然后搜索

```
用 JobFindsMe，根据 ~/Documents/resume.pdf，
找上海和杭州的 AI 应用工程师岗位，0-3 年经验。
```

不需要提供任何 ID 或参数——Core 自动处理一切。

### 💬 提示词模版（复制即用）

**有简历 — 自动解析 + 匹配：**

```
用 JobFindsMe，根据 [简历路径]，
找[城市]的[岗位方向]岗位。
```

示例：
```
用 JobFindsMe，根据 ~/Desktop/简历/董博.pdf，
找深圳和上海的 AI Agent 工程师岗位，20K 以上。
```

**没有简历 — 直接搜岗位（不匹配评分）：**

```
用 JobFindsMe，搜[城市]的[岗位方向]岗位。
```

示例：
```
用 JobFindsMe，搜北京的大模型应用开发岗位。
```

**启用招聘平台（BOSS/猎聘/智联/拉勾）：**

```
用 JobFindsMe，执行 setup，打开 Chrome 登录招聘平台。
```

**查看某个岗位详情：**

```
用 JobFindsMe，看一下第 3 个岗位的详细内容。
```

> 💡 每次搜索结果都包含：**岗位介绍、匹配度、投递链接、推荐理由** 四项，缺一不可。

**更新到最新版：**

```bash
jobfindsme self-update     # 升级
jobfindsme --version       # 查看版本
jobfindsme doctor          # 诊断（含版本 + Chrome 状态）

默认搜索不会启动 Chrome。字节、美团和 BOSS 等浏览器来源需显式启用。

**启用平台搜索（一次操作）：**

```bash
jobfindsme setup              # 打开 BOSS+猎聘+前程无忧+智联+拉勾 五个平台登录
jobfindsme setup --platform boss liepin  # 只开部分平台
```

岗位始终按固定格式返回，校招/社招和实习/正式分别标注：

```text
1. AI应用工程师｜示例科技｜上海｜社招｜正式｜匹配度 86%
   投递链接：https://careers.example.com/jobs/123

2. 大模型应用工程师实习生｜示例科技｜北京｜校招｜实习｜匹配度 81%
   投递链接：https://careers.example.com/jobs/456
```

---

## 为什么不用招聘 App？

| | 招聘 App | JobFindsMe |
|---|---|---|
| 搜索范围 | 一个平台 | **多个可验证来源统一搜索** |
| 简历 | 上传到平台 | **留在本地** |
| 推荐理由 | 黑盒算法 | **每条有证据**：技能→JD 对照 |
| 模型 API | — | **不需要**，Core 确定性匹配 |
| 数据导出 | 通常不支持 | **一键导出**，安全删除 |

---

## 来源覆盖

**五个平台，覆盖主流招聘渠道。** 腾讯、阿里、字节、拼多多、小米、网易、美团、携程、百度、京东、快手、蚂蚁、小红书、米哈游、B站、滴滴、SHEIN、华为、知乎……绝大部分中国互联网公司的岗位都能在这些平台上找到。

| 来源 | 技术 | 说明 |
|------|------|------|
| **BOSS直聘** | Chrome CDP | 岗位最多，明文薪资（需登录） |
| **猎聘** | Chrome CDP | 中高端岗位，外企中国岗（免登录） |
| **前程无忧** | Chrome CDP | 传统行业+IT，覆盖广（免登录） |
| **智联招聘** | Chrome CDP | 传统行业 + IT（免登录） |
| **拉勾** | Chrome CDP | 互联网专注（免登录） |

> 搜一次覆盖主流招聘渠道。不保证覆盖所有公司所有岗位——部分职位可能仅在官网或内推渠道发布。

---

## 怎么做到的

```
你说一句话
      │
      ▼
  Agent（ZCode / Codex / Claude Code）
      │
      ▼
  JobFindsMe MCP Server（本地）
      │
  ├── Chrome CDP ────────→ BOSS/猎聘/前程无忧/智联/拉勾
      └── BOSS CDP 桥 ───────────→ Experimental（显式启用）
      │
      ▼
  去重 → 硬过滤（地点/薪资/年限）→ 证据匹配 → Top 10 + 理由 + 链接
```

---

## MCP 工具

| 工具 | 做什么 |
|------|--------|
| `setup_profile` | 导入简历，自动确认 |
| `configure_search` | 设角色/城市/薪资/年限 |
| `search_jobs` | 搜索 + 匹配 |
| `get_jobs` | 翻页浏览 |
| `get_job_details` | 看单个岗位详情 |
| `update_job_state` | 收藏/忽略/已投递 |
| `configure_monitor` | 定时刷新 |
| `export_local_data` | 导出 |
| `delete_local_data` | 两阶段安全删除 |

---

## 隐私与安全

- 简历留本地，Agent 不读完整文件
- 只存结构化事实和最少证据
- BOSS 实验性 Connector 只连接用户显式启动的本地 Chrome CDP，不读取密码
- 删除需预览 + 确认令牌两步

---

## 免责声明

JobFindsMe 是本地工具，帮助整理和匹配你已登录、有权查看的岗位信息。使用产生的一切后果（含平台账号限制）由使用者承担。禁止商业转售、大规模爬取、绕过平台限制。

---

## 参与贡献

- 提交脱敏的错排/漏排/重复/失效岗位 Bad Case
- 增加合规的企业招聘官网 Connector
- 补充中文职位别名、地点、薪资样本

[Issue](https://github.com/russeell/jobfindsme/issues) · [PROJECT_SPEC.md](PROJECT_SPEC.md)

---

## License

[MIT](LICENSE)
