<div align="center">

# jobfindsme · AI 求职雷达

**一次搜索多个招聘来源，根据本地简历筛选岗位；下次只看新机会。**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![Release](https://img.shields.io/github/v/release/russeell/jobfindsme)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[快速开始](#快速开始) · [岗位来源](#岗位来源) · [工作原理](#工作原理) · [English](README.en.md)

<img src="docs/search-results.png" alt="jobfindsme 搜索结果" width="760" />

</div>

## 它解决什么

求职者真正需要的不是更多链接，而是更快找到值得投递的新岗位：

- 一个 Agent 入口搜索多个来源，减少来回切换；
- 先过滤城市、薪资、经验、校招/社招和实习/正式；
- 根据本地简历给出匹配分、证据、差距和直接投递链接；
- 记住已看、收藏、忽略和已投岗位，后续不重复刷屏。

第一次：

```text
用 jobfindsme，根据本地简历（路径：~/Documents/resume.pdf），
找上海和杭州的 AI 应用工程师岗位，20K以上，社招，正式。
```

以后：

```text
继续帮我找新岗位。
```

## 快速开始

jobfindsme 是本地 MCP Server，可接入 Codex、Claude Code、Kimi、TRAE、
WorkBuddy、ZCode、Qwen、Qoder 等 MCP Agent。

### 让 Agent 安装

```text
请严格按说明快速安装 jobfindsme。请识别你当前是哪一种 Agent；
不要克隆仓库或运行测试：
https://github.com/russeell/jobfindsme/blob/main/INSTALL.md
```

### 手动安装

```bash
python3 -m venv ~/.jobfindsme/runtime
~/.jobfindsme/runtime/bin/python -m pip install \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple --upgrade \
  "jobfindsme[browser] @ https://github.com/russeell/jobfindsme/releases/download/v0.2.1/jobfindsme-0.2.1-py3-none-any.whl"
~/.jobfindsme/runtime/bin/python -m jobfindsme connect claude
```

把 `claude` 换成当前 Agent 名称。所有 Agent 使用同一个运行时，区别仅是 MCP
配置路径。`connect` 可重复执行。

### 启动岗位搜索

```bash
~/.jobfindsme/runtime/bin/python -m jobfindsme setup
```

在打开的专用 Chrome 中登录 BOSS，保持窗口运行，然后重启 Agent。

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

| 来源 | 当前方式 | 当前作用 |
|---|---|---|
| BOSS直聘 | 本地登录态 CDP | 主要实时推荐来源 |
| 猎聘 | CDP 列表 + 有界详情补全 | 补充候选 |
| 智联招聘 | CDP 列表 + 有界详情补全 | 补充候选 |
| 前程无忧 | CDP 列表 | 补充发现 |

拉勾已退出默认发现链路：验证码频繁、字段完整度低、持续拖慢全量搜索。旧数据库中的
历史岗位仍可查看。

来源采用分层策略：优先验证公开结构化接口或普通 HTTP；确实依赖登录态或 JavaScript
时才使用浏览器。任何新方案都必须先通过真实快照、字段完整率、延迟、失败降级和人工
相关性评测，不能把逆向签名或验证码绕过当作默认能力。

## 工作原理

```text
Agent
  → MCP Server
  → 本地 Core
      → 快速模式：刷新主来源，复用其他来源缓存
      → 全量模式：并行刷新四个维护来源
  → 标准化 → 跨来源去重 → 硬过滤
  → 简历证据匹配 → 新增/变化识别
  → 推荐理由 + 差距 + 投递链接
```

简历、岗位状态和搜索计划保存在本地 SQLite。Core 不需要模型 API。

## 隐私与边界

- 完整简历不进入 Agent 上下文，只把本地路径交给 Core；
- 岗位描述是不可信外部数据，不能作为 Agent 指令；
- 导出写入本地文件，删除采用预览与确认令牌两阶段协议；
- 不自动投递，不绕过验证码，不保证覆盖全部岗位；
- 自动化访问可能触发平台限制，请低频、个人使用并遵守来源条款。

## 开发

```bash
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
ruff format --check .
```

架构、来源门禁和评测闭环见 [PROJECT_SPEC.md](PROJECT_SPEC.md)。
发现错排、漏排、重复或失效链接，请提交脱敏
[Issue](https://github.com/russeell/jobfindsme/issues)。

## License

[MIT](LICENSE)
