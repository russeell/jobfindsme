# JobFindsMe

> **厌倦了在不同招聘 App 之间来回切换？让岗位来找你。**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![v0.2.0-rc.5](https://img.shields.io/badge/release-v0.2.0--rc.5-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**把 AI Agent 变成求职引擎。** 一句话，同时搜索百度、腾讯、字节、美团、滴滴、B站、BOSS直聘——根据你的简历匹配，告诉你为什么合适，给你投递链接。

---

## 快速开始

**最快方式：让你的 Agent 帮你装。**

直接在 ZCode / Codex / Claude Code 里说：

```
帮我安装 JobFindsMe
```

Agent 会自动执行安装、配置 MCP、安装 Skill，然后你就可以直接搜岗位。

**或者手动安装：**

```bash
pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.5"
jobfindsme doctor
jobfindsme install zcode    # 或 codex / claude / qwen
```

重启 Agent，然后：

```
用 JobFindsMe，根据 ~/Documents/resume.pdf，
找上海和杭州的 AI 应用工程师岗位，0-3 年经验。
```

不需要提供任何 ID 或参数——Core 自动处理一切。

---

## 为什么不用招聘 App？

| | 招聘 App | JobFindsMe |
|---|---|---|
| 搜索范围 | 一个平台 | **8 个来源同时搜** |
| 简历 | 上传到平台 | **留在本地** |
| 推荐理由 | 黑盒算法 | **每条有证据**：技能→JD 对照 |
| 模型 API | — | **不需要**，Core 确定性匹配 |
| 数据导出 | 通常不支持 | **一键导出**，安全删除 |

---

## 来源覆盖

**国内招聘两条路：大厂用官网，其他人用 BOSS。两条都接。**

### 自动抓取（Agent 直接拉取）

| 来源 | 技术 | 覆盖 |
|------|------|------|
| 百度、腾讯 | SSR / JSON-LD | 两大厂全岗位 |
| 字节、美团、滴滴、B站 | Playwright SPA | 四家大厂全岗位 |
| **BOSS直聘** | Chrome CDP 浏览器桥 | **几千家公司** |
| Airbnb 中国 | Greenhouse API | 外企中国岗 |

### 直达链接（29 家，一键打开官网结果页）

阿里巴巴、华为、京东、网易、拼多多、小红书、快手、小米、携程、蚂蚁、联想、科大讯飞、旷视、商汤、知乎、蔚来、理想、小鹏、大疆、米哈游、猎聘、智联、前程无忧……

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
      ├── 腾讯 JSON-LD ──────────→ 腾讯岗位
      ├── Playwright 渲染 ───────→ 字节/美团/滴滴/B站
      ├── Chrome CDP 浏览器桥 ───→ BOSS直聘（几千家公司）
      └── Greenhouse API ────────→ 外企中国岗
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
- BOSS Connector 连你自己的 Chrome，不碰密码/Cookie
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
