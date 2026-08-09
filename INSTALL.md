# jobfindsme 安装指南

jobfindsme 由两部分组成：

- 本地运行时：搜索、匹配、追踪岗位，数据保存在 `~/.jobfindsme/`；
- Agent 插件：为 Codex、Claude、Cursor 提供同一份 Skill 和 MCP 工具。

核心功能不需要模型 API Key。猎聘无需登录；BOSS直聘需要可选的本地扫码登录；
智联招聘和前程无忧遇到安全校验时会明确降级，不会伪装成“没有岗位”。

## 1. 安装本地运行时

需要 Python 3.11 或更高版本：

```bash
python3 --version
curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh | bash
```

脚本只做三件事：创建 `~/.jobfindsme/runtime`、安装正式 Release wheel、初始化本地数据。
它不会克隆仓库、安装开发依赖或修改 Agent 配置。

## 2. 安装 Agent 插件

### Codex

```bash
codex plugin marketplace add russeell/jobfindsme --ref main
codex plugin add jobfindsme@jobfindsme
```

### Claude Code

```bash
claude plugin marketplace add russeell/jobfindsme
claude plugin install jobfindsme@jobfindsme
```

### Cursor

仓库已维护 Cursor 原生插件清单。市场上架完成前使用兼容入口：

```bash
jobfindsme connect cursor
```

重启 Agent 后，Skill 与 MCP Server 才会同时生效。

## 3. 验证

```bash
jobfindsme --version
jobfindsme doctor
```

预期版本为 `0.10.0`，MCP 自检应显示 `8 tools`。`required: true` 的检查必须通过。
`boss_login` 或浏览器来源未配置属于可选状态，不影响猎聘等 HTTP 来源。

然后直接对 Agent 说：

```text
用 jobfindsme，根据本地简历（路径：~/Documents/resume.pdf），
找上海和深圳的 AI 应用工程师，20K以上，社招，正式。
```

完整简历由本地 Core 解析。Agent 只应把路径传给 `setup_profile`，不得先读取全文。

## 4. 登录 BOSS直聘（可选）

对 Agent 说：

```text
帮我登录 BOSS直聘
```

或运行：

```bash
jobfindsme setup
```

扫码后保持专用 Chrome 窗口运行。这个 profile 与个人 Chrome 隔离；跳过此步仍可使用
无需登录的来源。

## 兼容安装

原生插件不可用时，`connect` 可以写入旧式 MCP 配置：

```bash
jobfindsme connect codex
jobfindsme connect claude
jobfindsme connect cursor
jobfindsme config                    # 打印标准 MCP JSON
jobfindsme connect --path <配置文件>  # 其他客户端
```

这是兼容路径，不是推荐安装方式。所有客户端共用同一个本地运行时和 SQLite 数据。

## 手动安装运行时

安装脚本不可用时：

```bash
python3 -m venv ~/.jobfindsme/runtime
~/.jobfindsme/runtime/bin/python -m pip install --upgrade \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  "jobfindsme[browser] @ https://github.com/russeell/jobfindsme/releases/download/v0.10.0/jobfindsme-0.10.0-py3-none-any.whl"
```

Release wheel 只从 GitHub 官方地址下载，依赖可通过清华 PyPI 镜像加速。

## 更新

重新运行安装脚本，然后更新插件：

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh | bash
codex plugin marketplace upgrade jobfindsme     # Codex：刷新市场快照
claude plugin update jobfindsme@jobfindsme      # Claude Code
```

数据库会自动迁移，历史岗位、状态和搜索条件保留。

## 卸载

先从 Agent 的插件管理器卸载；兼容安装则运行：

```bash
jobfindsme uninstall codex   # 或 claude / cursor
```

这只移除适配配置，不删除数据。彻底删除前先导出，再执行：

```bash
rm -rf ~/.jobfindsme
```

## 常见问题

**搜索结果为 0**

先对 Agent 说“检查 jobfindsme 来源并告诉我怎么恢复”，或运行 `jobfindsme doctor`。
系统应区分“来源失败”和“确实没有匹配岗位”。

**安装超过 5 分钟**

停止当前命令，保留最后输出并提交 Issue。不要让 Agent 克隆仓库、安装测试依赖或下载
整套浏览器来尝试修复。

**数据与隐私**

- 完整简历不应进入 Agent 上下文；
- 岗位描述按不可信外部数据处理；
- 不自动投递、不绕过验证码、不做大规模抓取；
- 本地数据可通过 MCP 的导出和两阶段删除工具管理。

发现安装或来源问题，请提交脱敏
[Issue](https://github.com/russeell/jobfindsme/issues)。
