# 自动开发安排

当前交接见 [HANDOFF](HANDOFF.md)，任务状态只认 [tasks.json](tasks.json)。D19 已完成 UI6 修复验收；随后按用户授权完成 D20 的本项目可恢复归档。追加 D21/D22/D23/D24 已在 UI9 完成，实施者停止写入并回传调度者；不重复派发已完成的配色或清理任务。

调度任务：`01a0b37c-a94a-76a0-a521-5fdfc6f3977c`。D13–D20 实施任务：`01a0b572-9785-75c3-be63-b5e5d8bc6f4b`，D19/D20 按用户指定 `gpt-6-astra / low` 执行。共享目录始终保持唯一写入者；普通开发不设人工代码 review。

代码目录：`/Users/russeell/Documents/开源项目开发/jobfindsme`，是独立嵌套 Git 仓库。父项目 worktree 不包含本仓库，不能误当代码副本。视觉基线为 `ui/jobfindsme-desktop.html` 的灰白设计；最新用户决定为岗位研究保留口碑调查与针对 JD 修改简历，删除应聘准备。

来源真实账号验证继续按 D01/D04 依赖执行；最终 D12 发行不得绕过这些依赖。没有新登录证据时不重复轮询或把官网可打开称为检索可用。2026-09-21 用户授权建立可验证的本地基线，此后每个独立修复验证通过后本地提交一次；继续禁止自动推送、发布、操作真实投递或移除旧 MCP 分发。保持唯一写入者，交接提供提交号及验收证据。

## 历史实施索引

下表只作历史定位，不是当前模型、调度或待办指令。原先包含多条“当前/下一轮”指令的完整历史已[可恢复归档](../../.development-archive/2026-09-19-d20/repo/docs/desktop/ORCHESTRATION.before-D20.md)。

| 范围 | 实施任务 | 主要证据 |
| --- | --- | --- |
| D13–D20 | 01a0b572-9785-75c3-be63-b5e5d8bc6f4b | [D19](evidence/D19.md)、[D20](evidence/D20.md) |
| D04d / D12b / D12c | 01a0b53e-846a-7da2-9628-dff4d557e562 | [D12b](evidence/D12b.md)、[D12c](evidence/D12c.md) |
| D10a / D11a / D04c / D12a | 01a0b520-db5a-76e3-8b65-1aa3409884bb | [D12a](evidence/D12a.md) |
| D10 / D11 | 01a0b4fc-0b95-7da2-b969-5a13a5ae0a54 | [D10](evidence/D10.md)、[D11](evidence/D11.md) |
| D05 / D06 | 01a0b4ea-f5a3-7b50-937f-27bb5f4f144f | [D05](evidence/D05.md)、[D06](evidence/D06.md) |
| D04a / D04b / D09复核 | 01a0b4cd-46b9-71b2-a1d8-c0c43c130487 | [D04a](evidence/D04a.md)、[D04b](evidence/D04b.md) |
| D07 / D09 | 01a0b4b6-2ac1-7122-b6d2-9a1c1522898d | [D07](evidence/D07.md)、[D09](evidence/D09.md) |
| D03 / D08及修复 | 01a0b455-4b09-7cf3-a7b0-29574dcfe419 | [修复证据](evidence/D03-D08-review-resolution.md) |
| D03 / D08只读审查 | 01a0b472-301b-7da2-95fa-2e1d8e0fcdfc | [审查](evidence/D03-D08-review.md) |
| D02及修复 | 01a0b42c-30ec-7f82-9466-090f253f207c | [修复证据](evidence/D02-review-resolution.md) |
| D02只读审查 | 01a0b440-c27e-7ec2-b5f1-3e23776fc23a | [审查](evidence/D02-review.md) |

新阶段按 DEVELOPMENT.md 与 tasks.json 选择，先完成具体实现和风险对应验证，必要时独立审查；不以反复全量测试或新增调度文档代替推进。
