# JobFindsMe

本地桌面求职工作台：找工作、口碑调查、简历管理、岗位记录与定时检索。
Electron/React 提供界面与隔离浏览器，Python 提供本地 API、检索、匹配和持久化。

## 核心功能

- **找工作**：选择招聘平台和公司官网，按关键词、求职条件与已确认简历检索和匹配；查看岗位详情，记录已读、收藏及投递状态。来源支持全选和批量检查，登录状态与检索能力分别显示。
- **口碑调查**：选择“公司评价”“岗位情况”，调查公开反馈、工作内容、工作强度、假期与福利。报告保存到岗位，支持再次查看和删除历史报告；证据附原始链接，缺失信息明确标注。
- **简历维护**：导入 PDF、DOCX、Markdown 或 TXT，核对内容、维护版本、预览和导出。简历用于检索与匹配；历史版本删除受当前版本及引用保护。
- **内嵌浏览器**：打开岗位原页、登录招聘平台，持久保存本应用会话；自动采集不可用时提供原页操作入口。不会自动投递。

## 当前状态与限制

当前为 macOS 本地开发版本，尚不是全部来源完成验收的正式发行版。

- 目录覆盖 4 个招聘平台与 16 家公司官网；“已收录”“已登录”“可打开官网”均不等于列表、续页和完整 JD 全部可检索。以应用中的实际检查结果为准。
- 平台可以要求重新登录或验证；应用不导入其他浏览器的登录状态，也不绕过验证码或限流。浏览器兜底不能保证自动提取成功。
- 智联登录后的列表、详情与续页仍有验收缺口；阿里详情资源访问仍存在已知问题。完整记录见[当前交接](docs/desktop/HANDOFF.md)。
- PDF 支持文本提取，扫描件暂无 OCR；旧 DOC 请先转为 DOCX。简历界面聚焦维护，不提供复杂对话改写或针对 JD 改写流程。
- 口碑报告整理公开来源中的陈述，不把用户评价当作确定事实，不作公司评分或推荐；内容可能因团队、岗位和时间而不同，请核对原文。
- 定时检索依赖本机应用运行；完全退出、关机或休眠时不会自动唤醒执行。

[桌面开发入口](docs/desktop/README.md) · [任务状态](docs/desktop/tasks.json) · [English](README.en.md)

## 本地运行

需要 Python 3.11+、Node.js/npm；桌面打包目前以 macOS 为验证环境。
在仓库根目录创建 `.venv`，桌面端默认从这里启动 Python 服务：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,browser]"
cd apps/desktop
npm ci
npm run build
npm start
```

已有其他 Python 环境时可用 `JFM_PYTHON` 指定解释器路径。普通启动使用现有应用数据目录；隔离验收请按[开发方案](docs/desktop/DEVELOPMENT.md)使用独立预览包，避免影响账号会话与用户数据。

## 检查与打包

```bash
# 仓库根目录，已激活 .venv
python -m pytest

# apps/desktop
npm test
npm run typecheck

# 打包前在 .venv 安装构建依赖
../../.venv/bin/python -m pip install pyinstaller
npm run build:python-runtime
npm run pack:mac:dir
npm run audit:mac:dir
```

默认目录包输出位于 `apps/desktop/release`。这些命令不执行签名、公证或发布；测试通过也不代表在线来源全部可用。

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
