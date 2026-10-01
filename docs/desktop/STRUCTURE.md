# 项目结构

```text
jobfindsme/
├── apps/desktop/       桌面应用
│   ├── main/           浏览器、来源采集、Agent 与本地服务连接
│   ├── renderer/       React 界面
│   ├── preload/        受限 IPC 桥接
│   ├── shared/         类型契约与共用逻辑
│   ├── skills/         应用技能及来源许可证
│   ├── tests/          桌面回归
│   └── scripts/        打包、审计与启动验证
├── src/jobfindsme/     Python 检索、研究、简历与 SQLite 服务
├── tests/              Python 回归
├── evaluation/         检索质量评测与合成样例
├── scripts/            Python 构建与数据验证
├── docs/
│   ├── desktop/        开发入口、模块说明与当前任务
│   └── images/         README 演示图
└── .github/workflows/  CI 与发行工作流
```

安装包只放 GitHub Releases，不进入源码树；本机缓存、用户数据、临时验收材料与个人开发 Skill 不提交。数据库迁移、应用技能和第三方许可证必须保留。

桌面端 `main/browser` 管浏览器会话，`main/sources` 管页面提取，`main/backend` 管 Python 进程与通信，`main/security` 管系统密钥；`renderer/src` 管找工作、研究、简历和设置。`main/index.ts` 与 `renderer/src/App.tsx` 负责组装。

桌面端 `skills/` 随包提供简历定制、模拟面试和公司/行业/技术主题深度研究工作流及 MIT 来源说明；`shared/assistant-skills.ts` 是固定注册表，`main/research/assistant-skills.mts` 只加载注册的技能。技能复用同一个 Pi Agent，通过 `read_skill` 按需读取，明确选择的技能由应用加载一次，其余由 Agent 按需读取；不改写用户提问。文件/文件夹由主进程原生选择，只读取支持的资料；Python复用文本提取器解析，不导入或覆盖简历。附件文本随对话保存在本机，点击发送才进入所选模型上下文。图片由主进程解码转JPEG，经Pi图片内容传入所选视觉模型，并受大小与历史预算限制。`main/research/research-subject.ts` 区分公司与主题锚点；主题证据不混入公司缓存，正式报告显式标注主题范围。深度研究沿用有界搜索、原文读取及引用校验。

检索共用底座：`main/sources/source-search-coordinator.ts` 有界读取、`source-search-execution.ts` 每批保存，`shared/search-scope.ts` 维护续查。每次只选一个城市或不限城市；首轮只用用户关键词，不调用模型。选中岗位才补 JD，`SourceBrowserManager.readResearchJob` 按工作区/来源/链接缓存详情。Agent 的 `search_jobs` 调用相同执行入口，返回已保存岗位及真实覆盖记录。

`main/research/public-retrieval.ts` 负责公开发现，`original-reader.ts` 负责有时效/工作区/会话范围的原文缓存及 HTTP → 应用浏览器回退。`browser-snapshot.ts` 生成正文和语义 DOM 元素引用；不是完整可访问性树。每个任务持有自己的标签页，沿用平台分区会话；导航刷新引用，只允许公开读取、同站 GET 搜索与链接翻页，登录/验证交给用户。`public-network.ts` 校验资源公网地址，不能回退绕过 TLS 错误。Python 按实际 MIME/文件签名处理 PDF，语义正文排除导航与验证页面。

Pi 的 `record_research` 保存子问题、连续原文支持的发现及缺口；后续轮次从同会话恢复，重复正文只算一份证据。检索、阅读、浏览器操作与模型调用共用预算及取消信号，末轮预留交付；综合分析失败仍保留已读片段。正式报告继续采用严格事实校验；自然回答的引用与 ID 校验不能替代完整语义事实核验。定时搜索保持原有停用状态，没有自动恢复历史计划。

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

求职助手发送错误按准备阶段和模型原因分别呈现；系统密钥只缓存成功解密的当前密文，进程退出即释放。原文 HTTP 阅读跟随已有网络代理并保留 TLS、公网地址与同站重定向校验；Python备用发现沿用原有直连服务，默认入口现由下述主进程检索路由负责。面试输出有一次有界格式修正，失败附件随未完成会话恢复。

`skills/web-retrieval` 是内部联网能力，自动用于检索/深度研究或由 Agent 按需读取，不增加第四个聊天模式。`main/research/public-retrieval.ts` 通过固定只读 HTTPS 适配器调用 Exa 官方远程 MCP 搜索接口，不依赖本机 Agent Reach/mcporter、不读取用户模型 Key、不启动本地 MCP 服务器；失败按同一截止时间调用既有 Python 发现服务，限流进入三分钟进程冷却。GitHub/论文为独立站点路由，原文仍由 Python 严格 HTTPS/公网/域名/跳转校验后读取；返回候选不携带证据ID或正文。邮箱、手机号、密钥和私人路径不得进入外部搜索词。

聊天任务由 `main/research/run-controller.ts` 按请求管理，renderer只显示当前会话的流与进度。`shared/research-chat-history.ts` 负责复制前缀的新分支及关系序列化，关系存入现有 conversation context；复制通过受限 preload clipboard IPC，不使用页面读写权限。

`renderer/src/preparation/JobPreparation.tsx` 是岗位准备卡；`shared/job-preparation.ts` 管阶段、目标匹配与显式入口草稿。`search/preparation.py` 与0040迁移保存工作区内阶段/下一步/日期/备注及岗位简历关联，复用既有job tracking和resume版本。`resume_editor/prompt.py` 的目标岗位提案保存为独立副本；通用编辑仍沿用原有基础版本规则。没有新增Agent或调度器。
