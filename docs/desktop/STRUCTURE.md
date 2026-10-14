# 项目结构

当前产品是本地桌面工作台。React 经受限 preload IPC 调用 Electron main；main 管理浏览器会话、模型和本机 Python HTTP 服务；Python 负责材料、检索规则与 SQLite。用户资料不在源码或安装包里。

```text
jobfindsme/
├── apps/desktop/
│   ├── main/           应用组装、浏览器、来源采集、模型与本地 API 客户端
│   ├── preload/        renderer 可调用的 IPC 白名单
│   ├── renderer/src/   找工作、岗位管理、我的简历、求职助手与设置
│   ├── shared/         类型契约与确定性共用逻辑
│   ├── skills/         随应用发行的技能与第三方许可证
│   ├── tests/          桌面行为与契约回归
│   └── scripts/        打包、审计、真实安装包隔离验收
├── src/jobfindsme/
│   ├── desktop_api/    本地认证 HTTP 接口
│   ├── sources/        来源目录、能力状态与准入
│   ├── connectors/     来源连接与 HTTP 列表适配
│   ├── search/         检索、排序、岗位准备、材料与执行记录
│   ├── profiles/       原件保管、后台文本索引与匹配事实
│   ├── resume_editor/  文档、提案、格式恢复与 Word/PDF 导出
│   ├── research/       公开发现、原文、引用与研究存储
│   └── migrations/     所有历史数据库迁移，必须保留
├── tests/              Python 回归
├── evaluation/         检索评测与合成样例
├── scripts/            Python 冻结与材料验收
├── docs/desktop/       当前入口、交接、结构与唯一任务清单
└── .github/workflows/  回归与发行流程
```

## 按业务找代码

| 业务 | 桌面入口 | Python 入口与约束 |
| --- | --- | --- |
| 检索与完整 JD | `main/sources/source-search-coordinator.ts`、`source-search-execution.ts`、`main/browser/source-browser.ts` | `search/intent.py`、`search/jobs.py`、`sources/`；来源准入由服务强制检查，失败保留成功结果 |
| 登录与来源检查 | `main/sources/source-check-queue.ts`、`source-actions.ts`、`main/browser/` | 来源状态与风险暂停持久化；网页可打开不等于列表、字段、分页可用 |
| 简历 | `renderer/src/resume/ResumePage.tsx`、`ResumeWordEditor.tsx`、`ResumeDocument.tsx` | `profiles/service.py`、`resume_editor/`；原件保持原字节，修改保存为独立版本 |
| 岗位准备与材料 | `renderer/src/preparation/JobPreparation.tsx`、`ApplicationPreparation.tsx`、`RecordsPage.tsx` | `search/preparation.py`；同岗位沿用准确简历版本、完整 JD、招呼语与下一步 |
| 面试与研究 | `main/research/pi-research-agent.mts`、`interview-materials.ts`、`public-retrieval.ts`、`original-reader.ts` | `research/`；预算、取消与引用检查，缺失材料明确说明 |
| BOSS 确认投递 | `main/applications/` | `search/application_attempts.py`；独立受限执行、快照、低频、去重及分别核验消息/附件 |
| 密钥与服务 | `main/security/secure-secret-store.ts`、`main/backend/python-service.ts`、`api-client.ts` | `desktop_api/app.py`；只监听本机并认证，密钥不进入日志/包/仓库 |

`main/index.ts`、`renderer/src/App.tsx` 和 `desktop_api/app.py` 负责组装。`main/ipc/register.ts`统一所有主窗口顶层frame调用来源检查，`ipc/resumes.ts`与`ipc/preparation.ts`注册简历和岗位材料；原preload名称保留。Python`desktop_api/resumes.py`与`schemas/resumes.py`独立维护16条简历路由和请求/响应，认证和原路径不变。TS简历契约在`shared/resume-contracts.ts`，由原`contracts.ts`兼容导出。新增逻辑优先放在对应业务模块，保持已有 IPC 名称、HTTP 路径与返回形状兼容。

## 简历、材料与版本

导入主流程展示原件，后台生成提取索引用于检索和 AI，不要求逐条勾选事实。旧确认 API 继续兼容已有数据库。自动索引不是用户核对事实的证明；模型材料标注提取误差。

编辑器使用 Tiptap。`shared/resume-editor-schema.ts` 与 Python `resume_editor/document.py` 限定文档节点和格式；`source_format.py` 从哈希一致的托管原件恢复可精确匹配的颜色、字号和粗体。PDF.js 展示原始 PDF 或实际导出的连续页面；编辑副本会重新排版，不保证任意 PDF/Word 原版式无损转换。Word 原件的文字预览不等于还原原始布局。

模板保存在每份版本的 `document.attrs.template` 中。`shared/resume-editor-actions.ts` 在同一事务设置正文与根属性，使模板也能撤销、写草稿和恢复。旧稿没有模板元数据时，界面要求保存排版后再预览/导出。`shared/resume-export.ts` 按准确版本读取，归档原件也可原字节导出；岗位材料和附件不得用新基础简历替换已选旧稿。“暂不附简历”是明确选择，不得静默回退；JobPreparationService.resume_selection保留隐藏记录中的选择，单独待办不计为材料选择。main/research/preparation-materials.ts共用有限原文段落选择，按岗位相关性纳入长材料末尾并保留原顺序；不是新的事实生成或匹配评分。

所有简历修改留在简历页。整份 AI 定制使用原提案与显式审阅；单段修改使用 `ResumeSelectionAI.tsx` 和 `shared/resume-selection-quality.ts`，有选区快照、过期保护与有限事实检查。确定性检查不能保证完整语义或所有事实正确；不自动覆盖原稿。草稿留在隔离的工作区/基础版本键下，正式保存创建新版本。

## 网络与执行边界

同条件只读请求由 `main/shared-flight.ts` 合并；每个调用方仍有自己的取消与等待预算。来源按平台串行、有界读取、缓存列表/JD和风险暂停；首轮手输关键词不调用模型，选中后才补完整 JD。定时搜索停用，保留历史读取与迁移兼容。

Agent 浏览器任务使用独立页与平台分区会话，只允许公开读取、同站 GET 搜索和链接翻页。`browser-snapshot.ts` 的语义 DOM 引用不是完整可访问性树。`public-network.ts` 及 Python 原文读取共同执行公网/TLS/跳转校验，不通过回退绕过 TLS 错误。公开发现候选不等于可引用原文；研究持久化发现和缺口，重复正文不重复计证据。

BOSS 单岗位确认投递是实验功能，真实只读预览已验证，真实附件上传与消息送达尚未验收。用户当前只授权预览，不能执行真实发送。删除显示记录不解除执行去重；结果不明、取消、验证码或限流时不重发。打开岗位原页不算已投递。

## 构建与历史

Node和Playwright使用 `apps/desktop/package-lock.json`，发行Python使用带SHA256的`requirements/release.txt`；`freeze_desktop_api.py`核对依赖并记录代码指纹。桌面构建也记录来源指纹，打包拒绝过期载荷。普通推送运行CI，包按需dispatch或tag构建；缓存仅下载依赖，不缓存用户资料、冻结后端或应用。Python 由 PyInstaller 冻结；`scripts/package-*.mjs` 写入来源提交并收集许可证，`audit-*-package.mjs` 拒绝数据库/会话/验收材料。`smoke-desktop.mjs` 在隔离虚构资料中验证真实 UI → IPC → 冻结 API → SQLite 和两次启动；只替换文件选择框返回路径，不使用真实账号或付费模型。

`apps/desktop/release/` 是忽略的本机产物目录，只保留当前 ZIP 和最近回退包；新验收应用与资料放系统临时目录。Windows ZIP 必须完整解压；两端当前未签名，Windows ARM 不在发行范围。发行包必须来自同一已验证提交，公开发布另行授权。

编辑器参考 Tiptap Simple Editor、Reactive Resume 和 Novel 的交互思路；解析参考 OpenResume 的设计，网络参考 Douyin_TikTok_Download_API 的连接复用思路，均为独立实现。依赖与技能许可证随包保留，详细设计来源和旧验收记录见 [固定历史快照](https://github.com/russeell/jobfindsme/blob/fc266518a0ae78986abb6572094ee8dff24f153f/docs/desktop/STRUCTURE.md)。旧 CLI/MCP 与历史方案已退役，不从历史恢复产品行为。
