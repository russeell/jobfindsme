---
name: jobfindsme-dev
description: 维护 JobFindsMe 桌面产品，按当前任务状态实现、验证和交付功能；不用于实际替用户投递或定时求职。
---

# JobFindsMe 开发

默认仓库：`/Users/russeell/Documents/开源项目开发/jobfindsme`。先读根目录 `AGENTS.md`、`docs/desktop/HANDOFF.md`、`docs/desktop/STRUCTURE.md`、`docs/desktop/tasks.json` 与 Git 状态。以当前代码和任务状态为准；旧计划及截图只在需要追溯时查固定历史提交。

用户要求实施时，选定明确的未完成事项，核对依赖，完成改动和最小有效验证。真实平台缺登录、验证码或受限时保持阻塞，继续独立可做的工作；不把打开官网当成自动检索成功。不触碰用户真实投递、付费服务、活跃会话或历史数据。数据库迁移不能按引用数清理。

每个独立修复通过后提交，并更新 `docs/desktop/HANDOFF.md` 和 `docs/desktop/tasks.json`。简短记录实际结果与限制；旧验收保留在 Git 历史，不再往当前仓库添加逐任务证据文件。用户偏好直接合入 main：先获取并合并最新远端 main，不强推；仓库规则阻止时才用英文 PR。发布另需用户授权。

开发入口见 `docs/desktop/README.md`。文档改动查链接；Python 行为查相关 pytest；桌面行为查相关 Node 测试、类型与构建；发行前再做完整回归和真实桌面主流程。
