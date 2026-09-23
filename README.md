# JobFindsMe

本地桌面求职工作台：找工作、口碑调查、简历管理、岗位记录与定时检索。
Electron/React 提供界面与隔离浏览器，Python 提供本地 API、检索、匹配和持久化。

## 当前状态

macOS 本地开发版本。来源能力与登录状态分别核验；BOSS、智联、前程无忧登录后完整链路仍有待验收项，不承诺全部来源可用。用户在平台原页完成投递，打开链接不算已投递。

- [桌面开发入口](docs/desktop/README.md) · [任务状态](docs/desktop/tasks.json)
- [职责与迁移清单](docs/desktop/STRUCTURE.md) · [技术方案](docs/desktop/TECHNICAL.md)
- [当前 UI 与验收](docs/desktop/ui/UI34-evidence.md) · [English](README.en.md)

## 本地开发

```bash
python -m pip install -e ".[dev,browser]"
cd apps/desktop
npm ci
npm run build
npm start
```

普通启动使用现有用户目录。隔离验收应按 [开发方案](docs/desktop/DEVELOPMENT.md) 创建独立预览包，不覆盖正在使用的应用或账号会话。

```bash
# 仓库根目录
python -m pytest
# apps/desktop
npm test
npm run build:python-runtime
npm run pack:mac:dir
npm run audit:mac:dir
```

打包要求已安装 PyInstaller；本地开发可用 `uv sync --extra dev --extra browser`。默认打包输出位于 apps/desktop/release，发布和签名不由这些命令完成。

## 项目目录

```text
apps/desktop/
  main/              index.ts + browser/ sources/ backend/ security/
  renderer/src/      App.tsx + search/ research/ resume/ settings/ shared/
  shared/            IPC 契约与两端共享纯函数
  preload/           受限桌面桥接
  scripts/ tests/     打包审计与回归
src/jobfindsme/
  desktop_api/       鉴权回环 API，保留现有组装入口
  search/ sources/   检索匹配、岗位记录、来源目录与准入
  profiles/ resume_editor/ research/
  connectors/ contracts/ importing/
  models/ scheduler/ migrations/ resources/
  storage.py privacy.py context.py workspaces.py taxonomy.py
  mcp/ cli.py ...    保留的兼容入口
scripts/              构建、历史数据与质量检查
tests/               Python 回归
evaluation/          匹配数据集及兼容行为评测
docs/desktop/        当前方案、任务及验收
docs/legacy/         CLI/MCP 兼容文档
```

## 保留的兼容入口

Python 分发名仍为 `agent-job-search`，CLI、MCP、安装脚本及其资源暂保留，避免破坏已有外部调用；旧插件市场清单已撤下。它们不作为桌面启动前置。参见 [兼容文档](docs/legacy/README.zh.md)。所有 SQLite 迁移、历史读取兼容和有效构建配置保留。

[贡献指南](CONTRIBUTING.md) · [安全说明](SECURITY.md) · [MIT License](LICENSE)
