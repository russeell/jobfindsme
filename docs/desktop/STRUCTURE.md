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

桌面端 `skills/` 随包提供简历定制、模拟面试和公司/行业/技术主题深度研究工作流及 MIT 来源说明；`shared/assistant-skills.ts` 是固定注册表，`main/research/assistant-skills.mts` 只加载注册的技能。技能复用同一个 Pi Agent，通过 `read_skill` 按需读取，明确选择的技能由应用加载一次，其余由 Agent 按需读取；不改写用户提问。文件/文件夹由主进程原生选择，只读取支持的资料；Python复用文本提取器解析，不导入或覆盖简历。附件文本随对话保存在本机，点击发送才进入所选模型上下文。图片由主进程解码转JPEG，经Pi图片内容传入所选视觉模型，并受大小与历史预算限制。`main/research/research-subject.ts` 区分公司与主题锚点；主题证据不混入公司缓存，正式报告显式标注主题范围。深度研究沿用有界搜索、原文读取及引用校验。

Python `sources/` 是来源目录和检索准入的权威位置，`search/` 负责编排与统一结果，`research/` 管有来源的报告，`profiles/` 与 `resume_editor/` 管简历数据，`desktop_api/` 提供本地接口。`migrations/` 必须保留，以读取已有用户数据。

旧 CLI/MCP、安装器和 Skill 已退役。Python 包内部的旧发行名与数据路径只用于现有桌面打包和用户数据迁移。历史设计和验收文件可从 [重构前提交](https://github.com/russeell/jobfindsme/tree/a3a714e17ea73adabd54d36821c46ebc8a924461/docs/desktop) 查阅，不在当前树重复保存。

### Windows x64 packaging

`.github/workflows/windows-release.yml` builds on Windows, runs the Python and
Node regressions, freezes the API with PyInstaller, and packages Electron with
`scripts/package-windows.mjs`. `scripts/audit-windows-package.mjs` checks required
runtime files and rejects local databases/session directories. A Playwright
Electron smoke test launches the packaged executable twice and verifies the
renderer → IPC → bundled API → SQLite bootstrap, with screenshots saved beside
the ZIP artifact. No live recruitment requests or paid model calls are used.

The portable ZIP must be fully extracted before starting `JobFindsMe.exe`.
Windows uses its user-profile ACLs rather than POSIX permission bits. The build
is currently unsigned; SmartScreen may warn. Chinese PDF export uses installed
Microsoft YaHei, SimSun or Microsoft JhengHei fonts. Windows ARM is not packaged.

搜索入口 `search/intent.py` 将输入与已保存偏好转换成统一意图，`search/jobs.py` 计算本地信号与冻结快照。桌面来源协调器并行不同平台，完成批次由现有 API 顺序落库；结束时统一重排。`scripts/benchmark-search.mjs` 只运行固定延迟模拟，不访问招聘网站。

`research/web_providers.py` 是默认关闭的 Exa/Jina 轻量适配层，沿用现有 URL 安全与时间预算；不接入招聘采集。Agent 的简历提案由 `resume_editor/prompt.py` 校验，`ResumeProposal.tsx` 只提供审阅和显式保存。面试状态随原会话 JSON 保存，无新增 Agent 或调度系统。

求职助手发送错误按准备阶段和模型原因分别呈现；系统密钥只缓存成功解密的当前密文，进程退出即释放。原文 HTTP 阅读跟随已有网络代理并保留 TLS、公网地址与同站重定向校验；搜索仍使用原有直连发现服务。面试输出有一次有界格式修正，失败附件随未完成会话恢复。
