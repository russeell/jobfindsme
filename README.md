# JobFindsMe

> **厌倦了在不同招聘 App 之间来回切换？让岗位来找你。**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![v0.2.0-rc.5](https://img.shields.io/badge/release-v0.2.0--rc.5-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**把 AI Agent 变成求职引擎。** 根据本地简历，从经过验证的企业招聘源发现岗位，给出匹配证据和官方投递链接。

---

## 快速开始

**最快方式：让你的 Agent 帮你装。**

直接在 ZCode / Codex / Claude Code / Kimi Code / TRAE / Qoder 里说：

```
帮我安装 JobFindsMe：https://github.com/russeell/jobfindsme/blob/main/INSTALL.md
```

Agent 会读取安装指南，自动执行安装、配置 MCP、安装 Skill。

**或者手动安装：**

```bash
pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.5"
jobfindsme doctor
jobfindsme install zcode     # ZCode
jobfindsme install codex     # Codex
jobfindsme install claude    # Claude Code
jobfindsme install qwen      # Qwen Code
jobfindsme install kimi      # Kimi Code
jobfindsme install trae      # TRAE
jobfindsme install qoder     # Qoder
jobfindsme install workbuddy # WorkBuddy
```

重启 Agent，然后：

```
用 JobFindsMe，根据 ~/Documents/resume.pdf，
找上海和杭州的 AI 应用工程师岗位，0-3 年经验。
```

不需要提供任何 ID 或参数——Core 自动处理一切。

**更新到最新版：**

```bash
jobfindsme self-update     # 升级
jobfindsme --version       # 查看版本
jobfindsme doctor          # 诊断（含版本 + Chrome 状态）

默认搜索不会启动 Chrome。字节、美团和 BOSS 等浏览器来源需显式启用。

**启用平台搜索（一次操作）：**

```bash
jobfindsme setup              # 打开 BOSS+猎聘+智联+拉勾 四个平台登录
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

**12 个自动 Connector。所有中国大厂岗位都通过 BOSS/猎聘/智联/拉勾覆盖，不需要手动链接。**

| 来源 | 类型 | 技术 |
|------|------|------|
| 百度、腾讯 | 官网直连 | SSR / JSON-LD |
| 字节、美团、滴滴、B站 | 官网直连 | Playwright SPA |
| **BOSS直聘、猎聘、智联、拉勾** | 平台 CDP | Chrome 浏览器桥 |
| Airbnb、Airwallex | ATS API | Greenhouse / Ashby |

> BOSS直聘 + 猎聘 + 智联 + 拉勾四个平台覆盖阿里、华为、京东、网易、拼多多、小红书、快手、小米、携程、蚂蚁、联想……所有大厂的岗位都在这四个平台上发。不需要逐个攻克官网。

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
      ├── 百度 SSR 解析 ────────→ 百度岗位
      ├── Playwright 渲染 ───────→ 字节/美团（明确启用）
      ├── Greenhouse/Ashby API ──→ 外企中国岗
      ├── Beta Connector ────────→ 滴滴/B站（显式启用）
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
