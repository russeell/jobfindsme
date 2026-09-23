# JobFindsMe 桌面端重构

最新本地交付：[UI33](/private/tmp/JobFindsMe-D45-UI33.app)。双主题紧凑调研、单条历史移除、20 来源有界检查和发现页来源全选/清空完成，见 [D42](evidence/D42.md)、[D43](evidence/D43.md)、[D44](evidence/D44.md)、[D45](evidence/D45.md)。沿用灰白配色；普通交付包未启动，用户既有会话未覆盖。任务状态以 [tasks.json](tasks.json) 为准。

| 文档 | 用途 |
| --- | --- |
| [重构方案](REFACTOR.md) | 做什么、保留什么、何时移除旧代码 |
| [技术方案](TECHNICAL.md) | 架构、目录、数据与实现约束 |
| [项目管理方案](DEVELOPMENT.md) | 分阶段推进、适量验证、交接 |
| [任务清单](tasks.json) | 后续管理 skill 的机器可读入口 |

开发主目录：`/Users/russeell/Documents/开源项目开发/jobfindsme`。
现有包名为 `agent-job-search`，Python 导入路径仍是 `jobfindsme`；最终品牌与发行入口在收尾统一。
另一目录 `jobfindsme-web-prototype` 仅作参考，不合并其数据库或整套实现。

优先级：来源真实可用 → 过滤与简历匹配正确 → 完成投递路径 → 简历编辑与研究 → 自动化体验。
各平台真实验证完成前，不对外宣称全部可用；下一任务按任务清单的依赖和状态选择。
