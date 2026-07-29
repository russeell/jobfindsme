# JobFindsMe · AI 求职引擎

> **5 大平台一站式搜索 · 本地简历智能匹配 · 投递链接直达**
>
> BOSS直聘 · 猎聘 · 前程无忧 · 智联招聘 · 拉勾

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![v0.2.0-rc.5](https://img.shields.io/badge/release-v0.2.0--rc.5-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**JobFindsMe** 是一个标准 MCP Server，让你的 AI Agent（Claude Code、Codex、Hermes、OpenClaw、Kimi、TRAE、Qoder、WorkBuddy、ZCode 等）变成求职引擎。接入五大招聘平台，一句话搜索，本地简历匹配，每条结果都有匹配度、推荐理由和直达投递链接。

- 🔍 **一站式搜索** — 同时搜 BOSS直聘、猎聘、前程无忧、智联、拉勾
- 📄 **本地简历匹配** — 简历不出本地，AI 自动解析技能/经验/学历
- 📊 **每条有证据** — 匹配度百分比 + 技能对照 + 推荐理由
- 🔗 **投递链接直达** — 点击即跳转官方岗位页
- 🔌 **标准 MCP** — 适用所有 MCP 兼容 Agent，无需逐个适配

---

## 为什么不用招聘 App？

| | 招聘 App | JobFindsMe |
|---|---|---|
| 搜索范围 | 一个平台 | **五大平台统一搜索** |
| 简历 | 上传到平台 | **留在本地** |
| 推荐理由 | 黑盒算法 | **每条有证据**：技能→JD 对照 |
| 模型 API | — | **不需要**，本地确定性匹配 |
| 数据导出 | 通常不支持 | **一键导出**，安全删除 |

---

## 快速开始

JobFindsMe 是一个标准 **MCP Server**，适配所有 MCP 兼容的 Agent（Claude Code、Codex、Hermes、OpenClaw、Kimi、TRAE、Qoder、WorkBuddy、ZCode……）。

### 1. 安装（最简单：跟 Agent 说一句话）

```
帮我安装 JobFindsMe：https://github.com/russeell/jobfindsme/blob/main/INSTALL.md
```

Agent 会自动完成安装、配置 MCP、安装 Skill。

### 2. 重启 Agent，然后搜索

```
用 JobFindsMe，根据 ~/Documents/resume.pdf，
找上海和杭州的 AI 应用工程师岗位，20K以上，社招，正式。
```

> ⚠️ **BOSS直聘需要登录，其他四个不需要。** 搜不到 BOSS 岗位？看下方登录教程。

---

### 🔐 BOSS直聘登录（只需一次）

BOSS直聘是岗位最多的来源，但需要你在 Chrome 里登录一次。登录态保存在本地，以后自动生效。

**三步完成：**

**①** 运行 `jobfindsme setup`，Chrome 自动打开登录页。

**②** 用 **微信扫码**、**BOSS直聘 App 扫码** 或 **手机号登录**：

![BOSS直聘登录](docs/boss-login.png)

**③** 登录成功后关掉 Chrome。以后搜索自动复用，无需再登。

> 💡 猎聘、前程无忧、智联、拉勾装完就能搜，无需 setup。

---

### 手动安装（可选）

如果 Agent 无法自动安装，或你需要更精细的控制。

**安装 Python 包：**

```bash
pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.5"
```

**配置 MCP — 推荐输出 JSON 自行粘贴（适用所有 Agent）：**

```bash
jobfindsme config          # 输出标准 MCP JSON → 粘贴到任意 Agent 配置
jobfindsme install --path ~/.your-agent/mcp.json  # 或直接写入
```

**快捷安装：**

```bash
jobfindsme install claude    # Claude Code
jobfindsme install codex     # Codex
jobfindsme install kimi      # Kimi Code
jobfindsme install trae      # TRAE
jobfindsme install zcode     # ZCode
jobfindsme install workbuddy # WorkBuddy
# Hermes / OpenClaw / Qoder → jobfindsme install --path
```

重启 Agent，然后搜索：

### 💬 提示词模版

**完整模板（`[]` 为可选，去掉不需要的行即可）：**

```
用 JobFindsMe，
根据 [简历路径]                     ← 有简历才写这行，自动解析匹配
找 [城市] 的 [岗位方向] 岗位        ← 必填
薪资 [最低K]-[最高K] 或 [金额] 以上   ← 可选，如 20K以上、20-40K
[校招 / 社招]                       ← 可选
[实习 / 正式]                       ← 可选
[0-3年 / 3-5年 / …] 经验            ← 可选
排除 [外包 / 996 / …]               ← 可选
```

**场景示例（直接复制改）：**

```bash
# 有简历，精确搜
用 JobFindsMe，根据 ~/Documents/我的简历.pdf，
找上海和深圳的 AI Agent 工程师岗位，25K以上，社招，正式，1-5年经验。

# 有简历，放宽搜
用 JobFindsMe，根据 ~/Documents/我的简历.pdf，
找杭州的大模型应用开发岗位，校招。

# 无简历，快速浏览
用 JobFindsMe，搜北京的自动驾驶算法岗位，30K以上，社招。

# 无简历，找实习
用 JobFindsMe，搜全国的 AI 产品经理实习岗位。

# 查看详情 / 保存
用 JobFindsMe，看一下第 3 个岗位的详细内容。
用 JobFindsMe，把第 1、4、6 个岗位存起来。
```

> 💡 每条结果包含：**岗位介绍、匹配度、投递链接、推荐理由**。有简历才出匹配分，没简历也能搜。

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
  Agent（Claude Code / Codex / WorkBuddy / ZCode / …）
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
