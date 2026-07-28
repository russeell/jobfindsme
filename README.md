# JobFindsMe

让现有 AI Agent 根据本地简历，从公开招聘来源发现、匹配并持续跟踪岗位。

- 本地优先：简历、收藏和投递状态保存在本机 SQLite
- 无模型依赖：不配置 API Key 也能完成完整确定性流程
- Agent 原生：支持 Codex、Claude Code、Qwen Code 和 MCP 客户端
- 证据匹配：每条技能理由同时关联简历证据和 JD 证据
- 持续发现：定时刷新已订阅来源，只推送新增匹配岗位

[English](README.en.md)

## 安装

```bash
python3 -m pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git"
jobfindsme doctor
jobfindsme install codex  # 或 claude / qwen
```

重启 Agent，然后直接说：

```text
使用 JobFindsMe，根据 ~/Documents/resume.pdf
帮我找上海的 AI 应用工程师岗位，优先企业官网，排除外包和驻场。
```

首次使用时，Agent 会让本地 Core 解析简历、请你确认事实并配置搜索。
用户不需要创建或管理 Workspace ID、Plan ID。

## 工作流

```text
本地简历路径
-> 本地解析与事实确认
-> 搜索条件与官方来源订阅
-> 发现、标准化、跨来源去重
-> 硬条件过滤与画像证据匹配
-> 岗位摘要、官方投递链接
-> 收藏 / 忽略 / 已投递
-> 可选定时刷新与飞书通知
```

## 当前来源

| 来源 | 状态 |
|---|---|
| Greenhouse 公开 Job Board API | 可用 |
| 单岗位 Schema.org `JobPosting` 页面 | 可用 |
| 用户提供的 CSV / JSON | 可用 |
| 需要登录、验证码或绕过反爬的平台 | 不支持 |

Web 页面、自动投递和云端账户系统不属于当前版本。

## 隐私与安全

- Agent 不应读取完整简历，只把本地路径交给 JobFindsMe。
- 岗位描述属于不可信外部数据，默认只返回短摘要。
- 完整 JD 需要显式查询单个岗位。
- 数据导出写入本地文件，Agent 只收到路径、Hash 和记录数量。
- 删除必须经过预览和短期确认令牌两步。
- HTTP 来源逐跳校验重定向，禁止本地、私网和凭据 URL。

## 开发状态

自动测试验证 Core、CLI、MCP、安装器、监控、隐私和安全边界。
合成数据只用于回归，不代表真实岗位匹配质量。真实来源兼容性与长期稳定性
以 [`reports/`](reports/) 中的验证记录为准。

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
ruff check .
ruff format --check .
```

产品边界和架构见 [`PROJECT_SPEC.md`](PROJECT_SPEC.md)。
项目采用 [MIT License](LICENSE)。
