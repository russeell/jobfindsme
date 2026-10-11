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

`renderer/src/preparation/JobPreparation.tsx` 是岗位准备卡；`shared/job-preparation.ts` 管阶段、目标匹配与显式入口草稿。`search/preparation.py` 与0040/0041迁移保存工作区内阶段/下一步/日期/备注、岗位简历关联及投递材料记录，复用既有job tracking和resume版本。`resume_editor/prompt.py` 的目标岗位提案保存为独立副本；通用编辑仍沿用原有基础版本规则。没有新增Agent或调度器。

`renderer/src/preparation/RecordsPage.tsx` 提供收藏/已投递/全部三项直接导航及本地记录筛选状态，`shared/records-view.ts` 负责收藏/投递分类与实际跟进/阶段、全部记录搜索与排序，先筛选再每批展示20条；不增加后端查询或模型调用。`resume/ResumeDialog.tsx` 使用原生dialog管理焦点与关闭，`ResumePage.tsx` 是固定“我的简历”入口，复用导入/核对、基础编辑、版本恢复与两种导出模板，以基础/岗位专属两类展示材料；待核对稿与当前版本分开显示。`ResumeDialogs.tsx` 提供独立预览导出、通用/目标岗位 AI 修改选择与焦点管理；`shared/resume-library.ts` 管章节、无实质改动判断、审阅数量和明确入口草稿。基础编辑按章节切换，旧版本并发更新时保留输入并阻止过期保存。`ResumeProposal.tsx` 在简历库、岗位准备、聊天中复用原文对照、接受/保留/重新审阅和显式版本保存。`ApplicationPreparation.tsx` 保存选定简历版本和开场白、复制/导出/打开原页及本人确认状态，不执行外部提交；确认后的材料保留为独立记录。`shared/job-follow-up.ts` 从原有准备日期生成今日待办，从会话已完成的面试状态生成复习项，点击练习只填写草稿。

`shared/discovery-filters.ts` 的 `simpleDiscoveryFilters` 仅用于精简搜索界面的条件、预检返回与续查，清除隐藏的退休条件并保留全职/兼职；界面类型筛选要求来源类型已知，历史快照与其他调用方沿用原契约。搜索界面保留城市、薪资、经验（含在校生/应届生）、工作类型、平台和直接未读开关。身份依据原文或来源实习/校招标记，由Python本地过滤，不调用模型。

简历导入 `profiles/parser.py` 保留本机个人信息与完整技能描述，Word换行按原文保留；`profiles/service.py` 将这些写入版本，匹配摘要只使用适合检索的已确认事实。Agent读取仍过滤个人信息并脱敏。`ResumeImportReview.tsx` 按原稿顺序连续核对，段落自动伸展，匹配标签默认折叠且不追加到正文；过期提案由 `ResumeProposal.tsx` 提示重新生成。`shared/assistant-quality.ts` 与 Pi 运行器为明确要求但缺失的简历提案提供预算内一次补交机会，最终保存仍需用户显式审阅。

D164：简历主页由外层 `.content` 统一滚动，弹窗正文单独滚动；`resume-library.ts` 与 Python `resume_editor/service.py` 同步社招/校招/紧凑章节顺序，旧classic导出兼容。`application-greeting.ts` 处理工作区招呼语占位替换，投递材料仍由现有服务保存、外部发送仍由用户完成。Agent岗位查询键包含当前所选来源，只有带岗位正文的查询结果才可复用为缓存，持久化游标不视为正文缓存。

简历纸张预览：`renderer/src/resume/ResumeDocument.tsx` 使用 PDF.js legacy 本地 worker 显示连续页面；`main/resume-preview.ts` 共用后端 PDF 导出并清理临时文件，预览与 PDF 同模板同排版。编辑/移动仍通过现有版本 API 保存，不覆盖原稿。

D167 简历文档编辑：`ResumeWordEditor.tsx` 在主页面用 Tiptap 开源核心直接编辑，`shared/resume-editor-schema.ts` 限定五个章节、段落、列表与文字格式；PDF/DOCX 导入仍先提取事实并核对，原文件保留，确认后统一进入文档。0042 迁移给不可变版本新增可选 document_json；`resume_editor/document.py` 验证节点、限制大小/深度并核对纯文本与结构一致。旧版本无需回写；原有 AI 提案/章节编辑仅替换变化条目，保留其余格式。Word 导出保留文字格式，PDF 继续使用实际导出的连续分页预览；编辑区为流式文稿，不宣称任意 PDF/Word 原版式无损转换或编辑区逐页所见即所得。

草稿按工作区与基础版本留在本机；显式保存生成新版本，并发版本冲突保留输入。`ResumeSelectionAI.tsx` 复用既有 Pi 单次润色通道，仅发送用户选中的一个段落，三个固定编辑目的、无工具、无联网搜索、45秒/1400输出tokens/不重试；建议需审阅、文档变化后禁止套用，采用支持撤销。整份岗位定制仍沿用原审阅机制。选段接口名沿用 polishGreeting，purpose 缺省时原招呼语逻辑不变。

参考 Reactive Resume 的[富文本工具栏](https://github.com/reactive-resume/reactive-resume/blob/main/apps/web/src/features/resume/editor/write/rich-text-editor.tsx)与[局部 AI 修改](https://github.com/reactive-resume/reactive-resume/blob/main/apps/web/src/features/resume/editor/write/improve.tsx)（MIT）；独立实现，没有复制源文件。Tiptap 3.31.4、ProseMirror 等编辑依赖的许可证由 `scripts/editor-licenses.mjs` 随 macOS/Windows 包收集，未引入其商业分页/协作服务。

D168：投递工作台分为材料/记录，0043 为 application_records 新增 deleted_at；删除/恢复按工作区和岗位限定，保留简历及独立投递状态，记录写入改为显式字段列表。简历空章节用 ProseMirror decoration 隐藏，仍保留原结构与添加入口；模板画廊沿用三种模板 ID，调整配色/间距/章节顺序，PDF/Word 不再增加泛称“简历”的额外标题。

简历 AI 对话框显式选择已验证模型并说明发送范围，生成按钮将单次请求带入既有 resume-tailor 会话/提案链路；nonce、页面/序列、输入/模型/技能检查防止重复或过期启动，生成不自动保存。DeepSeek 官方端点的短文本润色复用 Pi thinkingFormat=deepseek 显式关闭默认思考，不扩大请求预算或自动重试。参考 [Reactive Resume 富文本编辑](https://github.com/reactive-resume/reactive-resume/blob/main/apps/web/src/features/resume/editor/write/rich-text-editor.tsx)（MIT）、[Novel 的 AI 选区菜单](https://github.com/steven-tey/novel/blob/main/apps/web/components/tailwind/generative/ai-selector.tsx)（Apache-2.0），借鉴少量工具和先审阅后采用的交互，没有复制代码或新增编辑框架。DeepSeek 参数依据其[思考模式文档](https://api-docs.deepseek.com/guides/thinking_mode)。

D169：简历修改统一在 `ResumePage.tsx` 内运行与审阅；`ResumeOpenRequest` 将岗位/旧提案 ID 从岗位卡或助手带入。生成复用 runResearchChat IPC 与 resume-tailor 技能，但使用独立运行 ID、不写聊天列表；主进程仅为该技能提供 proposeResume。离开简历页或显式停止取消当前运行，过期响应丢弃；提案仍在本地持久保存。`ResearchPage` 不再嵌入可编辑的 ResumeProposal，旧记录提供简历页链接。D168 的 generateWith 自动进入聊天方案已移除。单段 AI、富文本编辑与所有导出沿用原实现。

D170：`shared/job-decision.ts` 汇总已有岗位/简历匹配证据，`search/JobDecision.tsx` 供搜索详情与岗位准备共用；没有新的网络或模型调用。`RecordsPage.tsx` 调用 `updateNextAction` IPC → `/v1/jobs/{job_id}/next-action` → `JobPreparationService.update_next_action`，事务内按工作区和更新时间校验，仅改下一步与日期；页面撤销持有精确回执，旧请求不能覆盖后续编辑。

D171：搜索详情的补全结果用既有 previewMatching 自动核对当前确认简历，不回写历史检索快照。`search/rules.py` 将明确“任选其一”的技能列表视为一组，独立要求仍分别核对。`main/research/interview-materials.ts` 只为当前面试运行复用成功的材料读取；Pi 对明确选中岗位的面试首请求带入有界JD/脱敏简历，仍使用原工作区及岗位关联接口，不新建聊天或材料存储框架。

D171 JD复用：`importing/repository.py` 保留元数据未变的30分钟内完整正文，避免新列表短摘要（含结构化列表）覆盖；不刷新正文读取时间，新的来源观察仍独立保存。

D172：`main/shared-flight.ts` 将同条件的只读请求合并为一次执行，每个调用方保留取消及等待时限，最后一个离开时取消底层请求；HTTP列表、浏览器列表及JD读取复用它。业务键不包含时间预算，工作区、平台、关键词、城市、页码和强刷区分。单次岗位检索的原有准入限制仍保留，没有新增并行Agent检索框架。

猎聘 `pure_http.py` 用明确错误码区分登录/验证、网络服务和结构变化；仅有效列表字段可表示空结果。连接器保留120秒内的匿名HTTP会话，失败丢弃；公开列表API按工作区/查询保留最多16个适配器，退出关闭，超时清理在后续请求时执行。队列等待和页面请求共用时间预算；取消本地HTTP等待不保证同步Python网络调用立即中断，后者受剩余预算限制。失败的后续页保留可重试游标，登录/验证阻塞除外。来源失败不被误报成本地API失败。

借鉴 Douyin_TikTok_Download_API v5 提交 `4f0bed8483c35a980315d9c7b3a1d4a1119ad2b2` 的错误分类、连接复用和请求合并思路，独立实现；未复制源码、未新增Redis/PostgreSQL/身份池。

工作台的页面滚动位置由 `App.tsx` 按工作区/页面保留在内存中；侧栏导航保留当前聊天，新建聊天单独触发。搜索页只跳转简历库，避免重复维护界面。`ResumeWordEditor` 统一模板和 PDF/Word 导出工具，`ResumeDocument` 的 managedToolbar 模式只显示页数/缩放与实际分页。

D174 简历导入：确定性解析器 v7 将项目/经历内行内“技术栈”“项目介绍”保留为正文，技能描述保留连续段落，正文不按相同文本去重；原先跳过的意向/评价/证书等保留为本机基本信息与补充内容。标签仍可单独核对并用于匹配，不自动添加为简历正文；仅标签的旧接口确认兼容。旧草稿与已保存版本不自动重写，重新导入时使用新解析版本。编辑/导出沿用已有五章节结构和模板，仍不还原任意 PDF 原版式。

参考 [OpenResume 的章节识别](https://github.com/xitanggg/open-resume/blob/4f8255a2c763479837f69f1dccf2a3338730cd79/src/app/lib/parse-resume-from-pdf/group-lines-into-sections.ts)和经历分组思路；该仓库为 AGPL-3.0，本轮仅阅读设计并独立实现，没有复制代码或引入依赖。


D175：导入主流程由 `ResumeOriginal.tsx` 展示原件，`ResumePage` 不再使用逐项事实确认组件。`profiles/service.py` 的 `index_original` 路径保留托管文件，在服务端自动生成用于匹配的索引版本；不改动文件或发起外部请求。原件版本由0044的 `original_file` 标识；旧版本默认false，手动/AI编辑新版本仍为false，恢复版本继承目标原件引用。`/v1/resumes/source/file` 只按工作区/文档ID读取哈希一致的托管文件，主进程受限IPC完成原件下载。

`ResumeDocument` 复用PDF.js显示原字节或已有导出预览；Vite把官方 CMaps、标准字体与解码器（含各自许可证）带入安装包，开发服务器仅提供固定资源映射。Word原件暂提供文字预览，不宣称版式还原。旧确认API保留兼容；内部自动索引状态不是“用户核对过”的证明，Agent材料明确标注提取误差。

`record_application` 同一事务更新岗位所选简历，面试沿用原有关联版本读取；`matching-preview` 支持工作区限定的指定版本，岗位准备传入同一关联ID。投递准备优先已关联版本，保留旧招呼语和未保存提示，不隐式发送或标记投递。新导入/基础编辑不会改动已有岗位材料。

D176 岗位记录使用 RecordsPage 原生表格与现有 JobActions/PopoverButton，不新增列表框架；窄工作区合并进度列。搜索反馈局部呈现，App 全局反馈区区分页面归属和服务状态；user-errors 先移除 Electron 包装再分类，保留敏感内容过滤。岗位准备移除重复决策块与其额外匹配读取。简历主界面隐藏版本编号并移除历史入口，内部版本、恢复API和材料关联仍保留。

macOS与Windows发行包由对应GitHub Actions从同一提交构建，包内package.json写入sourceCommit；包审计核对当前源码，共用smoke-desktop.mjs验证两次实际启动、四个导航入口和工作区保留。macOS使用Apple Silicon runner，不复用旧Electron外壳；Release只上传测试通过的产物。
