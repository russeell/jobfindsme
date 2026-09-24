# JobFindsMe 桌面端开发

D55 正在最终原生复验：双教育经历分组核对、紧凑来源选择、自由研究提问与居中阅读列已实现，见 [D55 证据](evidence/D55.md)。上一个完成任务为 D54，见 [D54 证据](evidence/D54.md)。窗口可自由伸缩，不固定 1:1；定时检索继续停用，旧计划和执行记录保留。任务状态以 [tasks.json](tasks.json) 为准。

| 文档 | 用途 |
| --- | --- |
| [重构方案](REFACTOR.md) | 做什么、保留什么、何时移除旧代码 |
| [技术方案](TECHNICAL.md) | 架构、目录、数据与实现约束 |
| [项目管理方案](DEVELOPMENT.md) | 分阶段推进、适量验证、交接 |
| [目录与清理清单](STRUCTURE.md) | 当前 tree、职责边界和保留理由 |
| [任务清单](tasks.json) | 后续管理 skill 的机器可读入口 |

开发主目录：`/Users/russeell/Documents/开源项目开发/jobfindsme`。
现有包名为 `agent-job-search`，Python 导入路径仍是 `jobfindsme`；最终品牌与发行入口在收尾统一。
另一目录 `jobfindsme-web-prototype` 仅作参考，不合并其数据库或整套实现。

优先级：来源真实可用 → 过滤与简历匹配正确 → 完成投递路径 → 简历编辑与研究 → 自动化体验。
各平台真实验证完成前，不对外宣称全部可用；下一任务按任务清单的依赖和状态选择。
