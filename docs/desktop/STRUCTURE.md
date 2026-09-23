# D47 目录归组与有限清理

## 范围与验收

2026-09-23 用户重新授权实际迁移和删除确认废弃文件。本轮只做目录归组、引用调整及插件市场清单撤下，不拆 desktop_api/app.py、main/index.ts 或 App.tsx，不改行为、数据库或来源会话。不恢复定时自动化。

目标目录：
```text
apps/desktop/
  main/index.ts               # 启动、组装及既有 IPC 注册
  main/browser/              # 标签、导航、会话
  main/sources/              # 页面解析、浏览器采集、检查队列
  main/backend/              # Python 进程/API、模型配置转发
  main/security/             # 系统密钥
  renderer/src/App.tsx        # 整体布局和全局状态
  renderer/src/{search,research,resume,settings,shared}/
  shared/                    # IPC 契约、两端使用的纯函数及导航策略
src/jobfindsme/
  desktop_api/               # 原 API 入口，不拆文件
  search/                    # 检索、匹配、计划、岗位记录
  sources/                   # 来源目录、订阅及检索准入
  profiles/ resume_editor/ research/
  connectors/ contracts/ importing/
  models/ scheduler/ migrations/ resources/
  storage.py privacy.py context.py workspaces.py taxonomy.py
```

Python sources 是来源目录和准入权威；Electron 保留导航白名单、页面适配常量与既有契约校验，不引入第二套检索规则。共享导航纯函数移到 desktop/shared，消除 renderer 间接导入 main 的路径。模型请求仍仅在 Python models 执行，Electron backend 只转发配置并协调密钥。

importing/repository.py 有多方依赖，本次不为路径整理重写持久化边界，后续可独立迁往存储层。profiles 包含偏好与资料，保留名称。resume_editor 仍负责版本、模板、导出和历史，不能整体删除。IPC 注册仍留 main/index.ts，拆注册另论。

## 精确迁移映射

| 原路径 | 新路径 |
| --- | --- |
| `src/jobfindsme/core/search.py` | `src/jobfindsme/search/orchestrator.py` |
| `src/jobfindsme/desktop_search.py` | `src/jobfindsme/search/desktop.py` |
| `src/jobfindsme/desktop_jobs.py` | `src/jobfindsme/search/jobs.py` |
| `src/jobfindsme/desktop_rules.py` | `src/jobfindsme/search/rules.py` |
| `src/jobfindsme/matching.py` | `src/jobfindsme/search/matching.py` |
| `src/jobfindsme/matching_prompts.py` | `src/jobfindsme/search/matching_prompts.py` |
| `src/jobfindsme/search_plans.py` | `src/jobfindsme/search/plans.py` |
| `src/jobfindsme/tracking.py` | `src/jobfindsme/search/tracking.py` |
| `src/jobfindsme/desktop_sources.py` | `src/jobfindsme/sources/desktop.py` |
| `src/jobfindsme/source_catalog.py` | `src/jobfindsme/sources/catalog.py` |
| `src/jobfindsme/source_subscriptions.py` | `src/jobfindsme/sources/subscriptions.py` |
| `apps/desktop/main/source-browser.ts` | `apps/desktop/main/browser/source-browser.ts` |
| `apps/desktop/main/source-browser-policy.ts` | `apps/desktop/shared/source-browser-policy.ts` |
| `apps/desktop/main/api-client.ts` | `apps/desktop/main/backend/api-client.ts` |
| `apps/desktop/main/python-service.ts` | `apps/desktop/main/backend/python-service.ts` |
| `apps/desktop/main/model-connection-service.ts` | `apps/desktop/main/backend/model-connection-service.ts` |
| `apps/desktop/main/secure-secret-store.ts` | `apps/desktop/main/security/secure-secret-store.ts` |
| `apps/desktop/main/boss-collector.ts` | `apps/desktop/main/sources/boss-collector.ts` |
| `apps/desktop/main/boss-page.ts` | `apps/desktop/main/sources/boss-page.ts` |
| `apps/desktop/main/company-page.ts` | `apps/desktop/main/sources/company-page.ts` |
| `apps/desktop/main/public-detail.ts` | `apps/desktop/main/sources/public-detail.ts` |
| `apps/desktop/main/source-actions.ts` | `apps/desktop/main/sources/source-actions.ts` |
| `apps/desktop/main/source-check-queue.ts` | `apps/desktop/main/sources/source-check-queue.ts` |
| `apps/desktop/main/research-extraction.ts` | `apps/desktop/main/sources/research-extraction.ts` |
| `apps/desktop/renderer/src/components/Discovery.tsx` | `apps/desktop/renderer/src/search/Discovery.tsx` |
| `apps/desktop/renderer/src/components/SearchFilters.tsx` | `apps/desktop/renderer/src/search/SearchFilters.tsx` |
| `apps/desktop/renderer/src/components/JobActions.tsx` | `apps/desktop/renderer/src/search/JobActions.tsx` |
| `apps/desktop/renderer/src/components/salary.ts` | `apps/desktop/renderer/src/search/salary.ts` |
| `apps/desktop/renderer/src/components/TasksPage.tsx` | `apps/desktop/renderer/src/search/TasksPage.tsx` |
| `apps/desktop/renderer/src/components/ResearchPage.tsx` | `apps/desktop/renderer/src/research/ResearchPage.tsx` |
| `apps/desktop/renderer/src/components/ReputationEvidence.tsx` | `apps/desktop/renderer/src/research/ReputationEvidence.tsx` |
| `apps/desktop/renderer/src/components/ResumePage.tsx` | `apps/desktop/renderer/src/resume/ResumePage.tsx` |
| `apps/desktop/renderer/src/components/MatchingRulesPage.tsx` | `apps/desktop/renderer/src/settings/MatchingRulesPage.tsx` |
| `apps/desktop/renderer/src/components/model-presets.ts` | `apps/desktop/renderer/src/settings/model-presets.ts` |
| `apps/desktop/renderer/src/components/Workbench.tsx` | `apps/desktop/renderer/src/shared/Workbench.tsx` |
| `apps/desktop/renderer/src/components/BrowserAddressBar.tsx` | `apps/desktop/renderer/src/shared/BrowserAddressBar.tsx` |
| `apps/desktop/renderer/src/components/BrowserStartPage.tsx` | `apps/desktop/renderer/src/shared/BrowserStartPage.tsx` |
| `apps/desktop/renderer/src/components/PopoverButton.tsx` | `apps/desktop/renderer/src/shared/PopoverButton.tsx` |
| `apps/desktop/renderer/src/components/Icon.tsx` | `apps/desktop/renderer/src/shared/Icon.tsx` |

## 删除候选与证据

- `.codex-plugin/plugin.json`、`.claude-plugin/{plugin,marketplace}.json`、`.cursor-plugin/plugin.json`、`.agents/plugins/marketplace.json`：旧求职插件市场入口；桌面 main/API/打包均不读取，唯一专属代码检查在 tests/plugins/test_plugin_distribution.py 的市场清单测试。本轮明确停止仓库插件市场分发，移除该专属测试，其余 CLI/安装/Skill 测试保留。
- `src/jobfindsme/core/__init__.py`：orchestrator 移走后为空包，不提供业务符号；所有引用迁移后删除。
- 旧 README 中插件安装宣传撤下；兼容 CLI 文档保留到 docs/legacy（移动而非复制）。不删除仍生效的命令和发布工作流。

## 明确保留

CLI/MCP/installer/doctor/branding/技能资源：pyproject scripts、python -m jobfindsme、CI、release、安装脚本和外部调用仍有效，整体退役需单独处理入口及外部兼容，不借无内部引用删除。保留 `.mcp.json`、skills/、安装脚本和对应测试。保留所有迁移、锁文件、许可证、核心评测、当前及历史验收、UI 视觉参考。未跟踪目录与用户文件不碰。

## 阶段

1. 路径迁移：导入解析、Python 回归、TS/Node 与构建通过后本地提交。
2. 有限删除与文档：保留兼容测试，校验分发入口和文档后本地提交。
3. 集成：重建 Python runtime 与 Electron 包，包资源/隐私审计和隔离原生启动；不执行真实批量检索，记录实际限制后提交证据。
