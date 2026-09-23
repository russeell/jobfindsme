# UI34 原生验收

日期：2026-09-23。隔离预览包 `/private/tmp/JobFindsMe-D46-UI34-QA33.app`；普通交付包 `/private/tmp/JobFindsMe-D46-UI34.app`。普通包未启动。截图均来自隔离应用，使用合成简历、岗位和报告；合成证据中的 `example.com` 链接只用于界面检查，不代表真实公司反馈。

| 场景 | 普通窗口 1162×768 | 窄窗 854×768 | 结果 |
| --- | --- | --- | --- |
| 找工作空态与下一步 | [调整前](evidence/UI34-default-find-before.jpg)、[调整后](evidence/UI34-default-find-after.jpg) | [找工作](evidence/UI34-narrow-find-after.jpg) | 搜索输入、来源入口与简历参与状态可见；空态收为单一指引。来源弹层在窄窗可滚动，含检查入口。 |
| 有内容岗位与动作 | [合成岗位](evidence/UI34-default-job-content.jpg) | 原生已看过页复核 | 标题、公司、城市、薪资状态、原页及报告动作可读；未进行真实投递。 |
| 调查入口 | [调整前](evidence/UI34-default-research-empty.jpg)、[调整后](evidence/UI34-default-research-after.jpg) | 主题卡在窄窗原生展开复核 | 历史报告默认收起，点击后稳定展开；两项主题可多选，无需额外必填文本。 |
| 有证据报告 | [合成报告](evidence/UI34-default-report-content.jpg) | [合成报告](evidence/UI34-narrow-report-content.jpg) | 公司评价与岗位情况各成一组，摘录旁有来源与日期，限制和 JD 线索按需展开。 |
| 无证据报告 | [无证据报告](evidence/UI34-default-report-zero.jpg) | 同一布局在窄窗复核 | 单一诚实空态，说明“没有查到”不等于不存在反馈。 |
| 来源检查 | [目录](evidence/UI34-default-sources.jpg)、[队列结果](evidence/UI34-default-source-check.jpg) | [目录](evidence/UI34-narrow-sources.jpg) | 队列逐源结果默认收起；预览包最多探测一个来源。完成后延迟通知计数问题已修复，复测 20/20、逐源 20 条。 |
| 简历 | 原生当前版本入口复核 | [预览与导出](evidence/UI34-narrow-resume-preview.jpg) | 当前简历先展示，历史和导出按需展开；“预览 / 导出”可直接定位预览区。 |

验证：`npm run build`、`npm test`（77/77）以及预览包/普通包 `audit:mac:dir` 通过。实际来源检查只在隔离预览中进行单源上限探测，猎聘列表本次通过；其余来源因登录或预算未探测，不据此声称可用。智联仍需在应用独立会话中由用户完成登录后再核对列表、详情与续页。未推送、发布、真实投递或调用付费模型。
