# 项目结构

这份目录图只列日常需要定位的入口。源码、迁移、测试和兼容命令仍按各自职责保留；历史重构的逐文件迁移表可从 [D47 时的文档](https://github.com/russeell/jobfindsme/blob/1beb7dbe4c465ade47452ae706de487a3582b0eb/docs/desktop/STRUCTURE.md) 找回。

```text
apps/desktop/
  main/               Electron 启动、浏览器、来源采集、Python 通信与密钥
  preload/            受限 IPC 桥接
  renderer/src/       找工作、岗位研究、简历弹层、设置与通用界面
  shared/             跨进程契约与纯函数
  public/ scripts/ tests/
src/jobfindsme/
  search/ sources/    检索编排、来源目录和准入
  research/           公开资料研究与报告
  profiles/ resume_editor/   简历资料、解析、版本与导出
  desktop_api/ contracts/ importing/ models/
  connectors/ migrations/ resources/
  scheduler/ mcp/     已停用的定时执行及现存兼容入口
tests/                 Python 回归测试
evaluation/            检索与匹配评测输入及工具
docs/                  面向用户和开发者的说明
scripts/               构建与检查工具
skills/                现存 CLI Skill
```

桌面 `main/browser` 管标签、导航和隔离会话，`main/sources` 管网页提取。Python `sources` 是来源目录与检索准入的权威位置，`search` 负责调度和统一结果；两端不各自维护一套岗位来源规则。`renderer/src/App.tsx` 和 `main/index.ts` 是组装入口，功能实现留在对应目录。

`docs/desktop/evidence/` 只跟踪简短的任务验收记录。历史截图、日志、JSON 和一次性脚本不参与运行、测试或打包，已移出当前 GitHub 文件树；记录中需要复查的附件链接指向不可变的历史提交。本机副本存放在忽略的 `.development-archive/2026-09-25-github-document-cleanup/`，不随仓库分发。

数据库迁移、CLI/MCP 兼容入口、构建配置、锁文件和现行测试不能仅凭目录名称或内部引用数删除。产品与实施状态以 [任务清单](tasks.json)、[交接](HANDOFF.md) 和 [开发流程](DEVELOPMENT.md) 为准。
