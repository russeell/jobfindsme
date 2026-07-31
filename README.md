<div align="center">

# jobfindsme · AI 求职雷达

**一句话同时搜 BOSS直聘、猎聘、前程无忧、智联招聘；按本地简历打分排序；之后只看新增和变化。**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![Release](https://img.shields.io/github/v/release/russeell/jobfindsme)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[快速开始](#快速开始) · [提示词模版](#提示词模版) · [岗位来源](#岗位来源) · [FAQ](#faq) · [English](README.en.md)

<img src="docs/search-results.png" alt="jobfindsme 搜索结果" width="760" />

</div>

---

第一次，你对 AI Agent 说一句：

```text
用 jobfindsme，根据本地简历（路径：~/Documents/resume.pdf），
找上海和杭州的 AI 应用工程师岗位，20K以上，社招，正式。
```

它同时搜四个平台，按你的简历逐条打分，附上推荐理由和投递链接。

以后，你只需要说：

```text
继续帮我找新岗位。
```

```text
第二天：
🆕 新增 3 个高匹配岗位
🔄 你收藏的 1 个岗位更新了技能要求
🔇 昨天看过的 10 个岗位，不再重复出现
```

<div align="center">
<img src="docs/demo.gif" alt="jobfindsme demo" width="860" />
</div>

## 为什么不用招聘 App

| 每天找工作时的重复劳动 | jobfindsme 的做法 |
|---|---|
| 在四个 App 之间来回切换 | 对 Agent 说一句话，四个平台一起搜 |
| 反复刷到同一个岗位 | 跨平台去重，记住已看、收藏、投递和忽略 |
| 不知道今天有什么新岗位 | 只汇报新增、变更、重开和关闭 |
| 推荐理由是黑盒 | 每条都有匹配分、命中证据、技能缺口和投递链接 |
| 求职状态散落在各平台 | 本地 SQLite 统一记录，随时导出、随时删除 |
| 不想注册一堆服务、配 API Key | 本地 Core 不需要任何模型 API Key |

## 什么时候不适合用它

说清楚比藏着掖着好：

- **你想海投** —— 它不做自动投递。帮你找到值得投的岗位，点链接自己投。
- **你要覆盖所有公司** —— 官网直投、内推、受访问限制的岗位仍会漏。
- **你不方便在本机跑 Chrome** —— BOSS 需要登录态；猎聘纯 HTTP 直连不需要浏览器，
  智联和前程无忧在被反爬挡住时需要浏览器降级。
- **你期待"录用概率预测"** —— 匹配分是可解释的确定性排序分，不是录用概率。

## 快速开始

jobfindsme 是本地 MCP Server，可接入 Claude Code、Codex、Kimi、TRAE、
WorkBuddy、ZCode、Qwen、Qoder 等 MCP Agent。

### 第 1 步：安装（二选一）

**让 Agent 自己装**——把这段话发给正在使用的 Agent：

```text
请严格按说明快速安装 jobfindsme。请识别你当前是哪一种 Agent；
不要克隆仓库或运行测试：
https://github.com/russeell/jobfindsme/blob/main/INSTALL.md
```

**或一行命令装**——把 `workbuddy` 换成你的 Agent（`claude` / `codex` / `kimi` /
`qwen` / `trae` / `zcode` / `qoder`）：

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh \
  | bash -s -- workbuddy
```

> [!NOTE]
> 脚本自动完成：检测 Python 3.11+ → 建独立运行时 → 装预编译包（依赖走清华镜像，
> GitHub 直连失败自动回退镜像源）→ 写入该 Agent 的 MCP 配置。可重复执行。

### 第 2 步：登录 BOSS直聘

```bash
~/.jobfindsme/runtime/bin/python -m jobfindsme setup
```

在打开的专用 Chrome 里扫码登录，保持窗口运行，然后重启 Agent。
（另外三个平台读公开搜索页，不用登录。）

### 第 3 步：开始搜

把第 1 句"第一次"的提示词发给 Agent 即可。

## 提示词模版

直接复制改参数：

```text
# 按简历找
用 jobfindsme 根据 ~/Documents/resume.pdf 找北京的 大模型应用工程师，30K以上，社招。

# 只看今天的新增
继续帮我找新岗位，只要今天新增的。

# 换条件
把城市换成深圳，薪资下限改成 25K，重新搜。

# 管理状态
把刚才第 2 个岗位标记为已投递；把外包公司全部忽略。
```

## 返回结果

每条推荐固定包含：

```text
大模型应用开发工程师｜示例科技｜上海｜25-40K｜社招·正式
匹配度：86%（排序分，不是录用概率）
适合你：RAG、Agent、FastAPI 与项目经历匹配
需要注意：岗位要求 Kubernetes，简历中未找到直接证据
投递：https://example.com/jobs/123
```

结果不足时不会用弱匹配岗位凑数；来源字段不完整时会明确标注。

## 岗位来源

每个来源采用三层降级链——先试纯 HTTP 直连（亚秒级），被反爬挡住就降级到浏览器
拦截，再不行就走 DOM 提取：

| 来源 | 纯 HTTP 直连 | 浏览器降级 | 作用 |
|---|---|---|---|
| BOSS直聘 | — | 本地登录态浏览器（CDP） | 主要实时推荐来源 |
| 猎聘 | ✅ `api-c.liepin.com` JSON API，~0.9s | CDP 拦截 → DOM | 亚秒级，无需浏览器 |
| 智联招聘 | ⚠️ 蜜罐检测中 | CDP 被动拦截 JSON → DOM | 补充候选 |
| 前程无忧 | ⚠️ WAF 检测中 | CDP 被动拦截 JSON → DOM | 补充发现 |

> [!NOTE]
> 猎聘纯 HTTP 已验证可用（42 岗位 / 0.96s）。智联和前程无忧的纯 HTTP 探测会
> 在 ~0.3s 内检测到反爬（蜜罐响应 / WAF2 挑战），自动降级到浏览器拦截——
> 降级对用户透明，只是从亚秒级变成多秒级。

拉勾已退出默认发现链路：验证码频繁、字段完整度低、持续拖慢全量搜索。旧数据库中的
历史岗位仍可查看。

> [!IMPORTANT]
> 来源采用分层策略：能用公开结构化接口就不用浏览器，必须登录或执行 JavaScript 时
> 才走本地浏览器；任何新来源都要先通过真实快照、字段完整率、延迟、失败降级和人工
> 相关性评测。**不把逆向签名或绕过验证码当作默认能力。**

## 工作原理

```text
Agent
  → MCP Server
  → 本地 Core
      → 纯 HTTP 直连（猎聘亚秒级；智联/51job 检测反爬 ~0.3s 后降级）
      → 浏览器 CDP 拦截（SPA 自带签名，被动读取 JSON）
      → DOM 提取（最终兜底）
      → 快速模式：刷新主来源，复用其他来源缓存
      → 全量模式：并行刷新四个来源
  → 标准化 → 跨来源去重 → 硬过滤（城市/薪资/校招社招/实习正式）
  → 简历证据匹配 → 新增/变化识别
  → 推荐理由 + 差距 + 投递链接
```

简历、岗位状态和搜索计划全部保存在本地 SQLite。Core 不需要模型 API。

## 隐私与安全

- 完整简历不进入 Agent 上下文，只把本地路径交给 Core 解析；
- 岗位描述按不可信外部数据处理，不作为 Agent 指令；
- 导出写入本地文件；删除走"预览 + 确认令牌"两阶段协议；
- 不自动投递、不绕过验证码、不承诺覆盖全部岗位。

## FAQ

**Q：四个平台都要登录吗？**
只有 BOSS 需要（扫码一次，后续复用本地登录态）。猎聘纯 HTTP 直连，不需要浏览器；
智联和前程无忧优先尝试纯 HTTP，被反爬挡住时降级到浏览器读取公开搜索页。

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
