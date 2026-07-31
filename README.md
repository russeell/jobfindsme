<div align="center">

# jobfindsme · AI 求职雷达

**一句话同时搜 BOSS直聘 + 猎聘，找到匹配你简历的岗位。**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![Release](https://img.shields.io/github/v/release/russeell/jobfindsme)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[快速开始](#快速开始) · [提示词模版](#提示词模版) · [岗位来源](#岗位来源) · [FAQ](#faq) · [English](README.en.md)

<img src="docs/search-results.png" alt="jobfindsme 搜索结果" width="760" />

</div>

---

对 AI Agent 说一句话，它同时搜 **BOSS直聘** 和 **猎聘** 两个平台，
基于你的简历做语义匹配，返回合适的岗位和投递链接：

```text
用 jobfindsme，根据本地简历（路径：~/Documents/resume.pdf），
找上海和杭州的 AI 应用工程师岗位，20K以上，社招，正式。
```

```text
✅ BOSS直聘·上海 ✓ · 猎聘·上海 ✓ (4.2s)
🆕 新增 6 个匹配岗位（已过滤 42 → 20）

1. AI应用工程师（Agent开发）｜某知名公司｜上海｜社招｜正式｜40K-60K
   技能：Agent、Python ｜ 经验：3-5年 ｜ 学历：本科
   推荐理由：JD 要求 Agent 开发与你的 LangGraph 项目经历直接匹配
   🔗 [投递链接](https://www.liepin.com/job/1980438233.shtml)

2. AI应用工程师 ｜上汽云计算中心 ｜上海｜社招｜正式｜25K-40K
   技能：RAG、Python ｜ 经验：3-5年 ｜ 学历：本科
   推荐理由：RAG 技能与你的知识库项目高度重叠，薪资符合预期
   🔗 [投递链接](https://www.liepin.com/job/1965405095.shtml)

3. AI应用工程师（CAD方向）｜极芯拓方 ｜上海浦东｜社招｜正式｜40K-70K
   技能：Python ｜ 经验：1-3年 ｜ 学历：本科
   推荐理由：方向略偏 CAD，但薪资上限高、可考虑
   🔗 [投递链接](https://www.liepin.com/job/1981816455.shtml)
```

每个岗位的**事实、信号和链接由 Server 固定生成（任何 Agent 一致）**，
推荐理由由 Agent 基于这些信号与你的简历生成。

<div align="center">
<img src="docs/demo.gif" alt="jobfindsme demo" width="860" />
</div>

## 使用方式

| 你想做什么 | 你只需要说 |
|-----------|-----------|
| **找岗位** | `用 jobfindsme 根据我的简历找上海的 AI 应用工程师，20K以上` |
| **定时推送** | `每天早上 9 点推送新岗位给我`（任意时间任意频率） |
| **查历史** | `我昨天看过的岗位有哪些？我之前投过哪些？` |

其余全部自动完成：跨平台去重、已看/已投的岗位不重复推荐、投递状态记录
（说一句「标记第 2 个为已投递」即可）、本地保存无需注册。

> 💡 **没有简历也能搜**——直接说条件和偏好即可（如"找上海的 AI 应用工程师
> 20K以上"）；提供简历路径会让匹配更精准（技能重叠、经验学历对比）。
- 本地保存，无需注册、无需 API Key

（内部机制：硬过滤 → 信号提取 → 粗排 Top-20 → Agent 语义精排 → 增量雷达。详见 [工作原理](#工作原理)。）

## 为什么不用招聘 App

| 每天找工作时的重复劳动 | jobfindsme 的做法 |
|---|---|
| 在 App 之间来回切换 | 对 Agent 说一句话，两个平台一起搜 |
| 反复刷到同一个岗位 | 自动记住已看、已投、已忽略 |
| 投递过的不记得，又投一遍 | 标记已投递 → 永不重复推荐 |
| 不知道今天有什么新岗位 | 定时推送，只汇报新增和变化 |
| 推荐理由是黑盒 | Agent 语义匹配，附理由和投递链接 |
| 求职状态散落在各平台 | 本地 SQLite 统一记录，可导出可删除 |

## 什么时候不适合用它

说清楚比藏着掖着好：

- **你想海投** —— 它不做自动投递。帮你找到值得投的岗位，点链接自己投。
- **你要覆盖所有公司** —— 官网直投、内推、受访问限制的岗位仍会漏。
- **你不方便在本机跑 Chrome** —— BOSS 需要登录态；猎聘纯 HTTP 直连不需要浏览器。
- **你期待"录用概率预测"** —— 匹配分是可解释的确定性排序分，不是录用概率。

## 快速开始

### 🗣️ 最简单：和 Agent 聊天就能装（推荐）

**什么都不用下载、不用敲命令。** 把这段话发给你的 AI Agent
（Claude Code / Codex / ZCode / Kimi / Qwen / TRAE 等）：

```text
请严格按说明快速安装 jobfindsme。请识别你当前是哪一种 Agent；
不要克隆仓库或运行测试：
https://github.com/russeell/jobfindsme/blob/main/INSTALL.md
```

Agent 会自动完成检测环境、安装、写入自己的 MCP 配置。**你只需要重启 Agent**，
然后对它说：

```text
用 jobfindsme，根据我的简历找上海的 AI 应用工程师，20K以上，社招。
```

> 想自己动手？也可以一行命令安装（`curl ... | bash -s -- codex`），
> 完整说明见 [INSTALL.md](INSTALL.md)。

### 登录 BOSS直聘（可选）

```bash
~/.jobfindsme/runtime/bin/python -m jobfindsme setup
```

在打开的专用 Chrome 里扫码登录，保持窗口运行，然后重启 Agent。

> 💡 **跳过这步也能用**——猎聘纯 HTTP 直连，不需要浏览器也不需要登录。
> 先用猎聘看看结果，觉得岗位不够再补上 BOSS。

## 提示词模版

**三个核心场景**（直接复制改参数）：

```text
# ① 找岗位
用 jobfindsme 根据 ~/Documents/resume.pdf 找北京的 大模型应用工程师，30K以上，社招。

# ② 定时推送（任意时间任意频率）
每天早上 9 点推送新岗位给我。
每周一晚上 8 点推送。
每两天推一次。

# ③ 查询历史匹配过的岗位
我之前看过的岗位有哪些？
我投过哪些岗位？
昨天推送的岗位还在吗？
```

**进阶**（可选）：

```text
# 只看今天的新增
继续帮我找新岗位，只要今天新增的。

# 换条件
把城市换成深圳，薪资下限改成 25K，重新搜。

# 管理状态
把刚才第 2 个岗位标记为已投递；把外包公司全部忽略。
```

## 返回结果

Agent 基于 MCP Server 提供的结构化岗位信号和粗筛分数做语义分析，每次推荐包含：

```text
大模型应用开发工程师｜示例科技｜上海｜社招｜正式｜25-40K
技能：RAG、Agent、FastAPI ｜ 经验：3-5年 ｜ 学历：本科
推荐理由：JD 要求 RAG、Agent、FastAPI，与你的简历高度重叠
需要注意：JD 要求 Kubernetes 经验，简历中未找到直接证据
🔗 [投递链接](https://example.com/jobs/123)
```

每个岗位固定包含：**事实行 + 信号行 + 推荐理由 + 可点击的投递链接**。
其中事实、信号和链接由 Server 确定生成（任何 Agent 完全一致）；推荐理由
由 Agent 基于信号与简历生成（措辞因模型而异，但依据相同）。

结果不足时 Agent 不会用弱匹配岗位凑数；来源字段不完整时会明确标注。

## 岗位来源

**默认双平台**：从 v0.3.1 起精简为 BOSS直聘 + 猎聘。两者覆盖了中国技术岗位市场的绝大部分，
维护成本与稳定性远优于四平台并存。

| 来源 | 方式 | 速度 | 需要浏览器？ |
|---|---|---|---|
| **BOSS直聘** | 本地 Chrome CDP，XHR 注入内部 API | ~0.9s | ✅ 需要（登录态） |
| **猎聘** | `api-c.liepin.com` 纯 HTTP JSON API | ~1.2s | ❌ 不需要 |

## 工作原理

```text
Agent (Claude/GPT/Qwen — 负责语义精排)
  → MCP Server (本地 stdio)
  → 本地 Core
      → 纯 HTTP 直连（猎聘亚秒级）
      → 浏览器 CDP 拦截（BOSS直聘 SPA 自带签名，被动读取 JSON）
      → 快速模式：刷新主来源，复用其他来源缓存
      → 全量模式：并行刷新双平台
  → 标准化 → 跨来源去重 → 硬过滤（城市/薪资/校招社招/实习正式）
  → 信号提取 + 加权粗筛（技能/经验/学历/活跃度/薪资）
  → 增量雷达（新增/变化/重开/关闭识别）
  → Agent 收到 Top-20 粗筛后的结构化岗位数据，自己做语义精排
```

MCP Server 做三件事：硬过滤、结构化信号提取、确定性粗筛（技能权重 50%、
经验 25%、学历 10%、活跃度 5%、薪资 5%）。Agent 用自己的 LLM 做最终语义排序。
这遵循了 MCP 架构最佳实践：Server 提供结构化数据，Agent 负责理解决策。
若合格岗位 ≤20 个，跳过粗筛，全量交给 Agent。

简历、岗位状态和搜索计划全部保存在本地 SQLite。Core 不需要模型 API。

## 隐私与安全

- 完整简历不进入 Agent 上下文，只把本地路径交给 Core 解析；
- 岗位描述按不可信外部数据处理，不作为 Agent 指令；
- 导出写入本地文件；删除走"预览 + 确认令牌"两阶段协议；
- 不自动投递、不绕过验证码、不承诺覆盖全部岗位。

## FAQ

**Q：平台都要登录吗？**
只有 BOSS 需要（扫码一次，后续复用本地登录态）。猎聘纯 HTTP 直连，不需要浏览器；

**Q：会不会封号？**
它做的是低频、拟人节奏的读取，不批量抓取、不自动操作。但自动化访问在平台条款里
都属于灰色地带，存在账号被限制的可能——请个人低频使用，风险自负。

**Q：搜索结果为什么是 0 / 某个平台经常没有结果？**
先跑 `jobfindsme doctor` 自检。BOSS 检查登录态是否过期；其余平台可能触发验证码，
系统会降级或明确标注使用缓存，不会静默给你空结果。

**Q：简历会被上传吗？**
不会。简历只在本地解析成结构化事实存入 SQLite，完整简历文本不进入 Agent 上下文。
`export_local_data` / `delete_local_data` 可随时导出和清除。

**Q：和直接把简历发给 AI 让它搜，有什么区别？**
通用 Agent 没有平台接入、没有跨天去重和状态记忆、也不能稳定解析 PDF 简历成结构化
事实。jobfindsme 把这三件事做成了确定性的本地服务，Agent 只负责对话。

## 开发

```bash
python -m pip install -e ".[dev]"
python -m pytest
ruff check . && ruff format --check .
```

架构、来源门禁和评测闭环见 [PROJECT_SPEC.md](PROJECT_SPEC.md)。
发现错排、漏排、重复或失效链接，请提交脱敏
[Issue](https://github.com/russeell/jobfindsme/issues)。

## 免责声明

- 本项目为免费开源的个人学习工具，帮助整理你**已登录、有权查看**的岗位信息；
- 自动化访问招聘平台可能触发对方风控，由此产生的账号限制、封禁等后果由使用者
  自行承担，与作者无关；
- 禁止用于商业转售、大规模爬取或绕过平台限制；
- 平台页面结构随时可能变化导致某个来源失效，请通过 Issue 反馈，作者会尽力跟进。

## License

[MIT](LICENSE)
