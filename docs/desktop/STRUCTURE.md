# 项目结构

```text
apps/desktop/       Electron 桌面端：窗口、持久浏览器会话、界面与 IPC 契约
src/jobfindsme/      Python 本地服务：检索、来源、研究、简历与 SQLite 迁移
tests/              Python 功能与桌面 API 测试
evaluation/         当前 CI 使用的检索质量评测与样例
scripts/            构建与验证脚本
docs/desktop/       当前开发状态、模块边界与任务清单
docs/images/        README 使用的界面截图
```

桌面端 `main/browser` 管浏览器会话，`main/sources` 管页面提取，`main/backend` 管 Python 进程与通信，`main/security` 管系统密钥；`renderer/src` 管找工作、研究、简历和设置。`main/index.ts` 与 `renderer/src/App.tsx` 负责组装。

Python `sources/` 是来源目录和检索准入的权威位置，`search/` 负责编排与统一结果，`research/` 管有来源的报告，`profiles/` 与 `resume_editor/` 管简历数据，`desktop_api/` 提供本地接口。`migrations/` 必须保留，以读取已有用户数据。

旧 CLI/MCP、安装器和 Skill 已退役。Python 包内部的旧发行名与数据路径只用于现有桌面打包和用户数据迁移。历史设计和验收文件可从 [重构前提交](https://github.com/russeell/jobfindsme/tree/a3a714e17ea73adabd54d36821c46ebc8a924461/docs/desktop) 查阅，不在当前树重复保存。
