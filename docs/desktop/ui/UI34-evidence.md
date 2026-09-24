# UI34 原生验收

日期：2026-09-23。隔离预览包 `/private/tmp/JobFindsMe-D46-UI34-QA33.app`；普通交付包 `/private/tmp/JobFindsMe-D46-UI34.app`。本任务未启动普通交付包。截图均来自隔离应用，使用合成简历、岗位和报告；合成证据中的 `example.com` 链接只用于界面检查，不代表真实公司反馈。

| 场景 | 普通窗口 1162×768 | 窄窗 854×768 | 结果 |
| --- | --- | --- | --- |
| 找工作空态与下一步 | [调整前](evidence/UI34-default-find-before.jpg)、[调整后](evidence/UI34-default-find-after.jpg) | [找工作](evidence/UI34-narrow-find-after.jpg) | 搜索输入、来源入口与简历参与状态可见；空态收为单一指引。来源弹层在窄窗可滚动，含检查入口。 |
| 找工作非空列表与详情 | [12 条合成结果](evidence/UI34-default-discovery-content.jpg) | [详情](evidence/UI34-narrow-discovery-detail.jpg)、[返回列表](evidence/UI34-narrow-discovery-list-return.jpg) | 通过生产找岗位界面加载受控快照；选择第 2/3 项更新详情，窄窗返回列表保留第 3 项选择。下文记录独立滚动和浏览器恢复。 |
| 已看过岗位与动作 | [已看过页合成岗位](evidence/UI34-default-job-content.jpg) | 原生已看过页复核 | 此旧截图仅证明已看过页，不再用作 Discovery 非空验收。 |
| 调查入口 | [调整前](evidence/UI34-default-research-empty.jpg)、[调整后](evidence/UI34-default-research-after.jpg) | 主题卡在窄窗原生展开复核 | 历史报告默认收起，点击后稳定展开；两项主题可多选，无需额外必填文本。 |
| 有证据报告 | [合成报告](evidence/UI34-default-report-content.jpg) | [合成报告](evidence/UI34-narrow-report-content.jpg) | 公司评价与岗位情况各成一组，摘录旁有来源与日期，限制和 JD 线索按需展开。 |
| 无证据报告 | [无证据报告](evidence/UI34-default-report-zero.jpg) | 同一布局在窄窗复核 | 单一诚实空态，说明“没有查到”不等于不存在反馈。 |
| 来源检查 | [目录](evidence/UI34-default-sources.jpg)、[队列结果](evidence/UI34-default-source-check.jpg) | [目录](evidence/UI34-narrow-sources.jpg) | 队列逐源结果默认收起；预览包最多探测一个来源。完成后延迟通知计数问题已修复，复测 20/20、逐源 20 条。 |
| 简历 | 原生当前版本入口复核 | [预览与导出](evidence/UI34-narrow-resume-preview.jpg) | 当前简历先展示，历史和导出按需展开；“预览 / 导出”可直接定位预览区。 |

验证：`npm run build`、`npm test`（77/77）以及预览包/普通包 `audit:mac:dir` 通过。实际来源检查只在隔离预览中进行单源上限探测，猎聘列表本次通过；其余来源因登录或预算未探测，不据此声称可用。智联仍需在应用独立会话中由用户完成登录后再核对列表、详情与续页。未推送、发布、真实投递或调用付费模型。

## 非空 Discovery 与原生浏览器补充验收

协调审核指出原“有内容岗位”截图来自已看过页，不能覆盖本轮修改的 Discovery。本次仅补该缺口，生产代码无改动，交付包仍为 `/private/tmp/JobFindsMe-D46-UI34.app`，代码提交 `cf29972`、`0b2b664`；未重包或重复运行已通过的测试。

隔离方式：从 QA33 的合成 SQLite 数据创建 `/private/tmp/jfm-ui34-discovery-profile`，只复制数据库，不复制登录资料。临时副本 `/private/tmp/JobFindsMe-D46-UI34-DiscoveryQA.app` 的测试入口覆盖 bootstrap 与搜索 IPC：仅提供“离线合成验收”来源，搜索返回用生产 `DesktopJobService.create_snapshot/page` 创建的本地快照。生产 renderer 的全部 6 个文件与普通交付包 SHA-256 逐一相同；JS 为 `f22219a3d64440bc896f13e7de5e3b060fbc02bd33e088806ea732a9320ff302`，CSS 为 `b9917e39a4923ab88a7c6e163cf5ffc15544968296b5f68cd295f6c1185ea3e4`。筛选、阅读状态及原生浏览器走原有实现。测试副本和注入入口未加入交付包。

数据：12 个明确标注为合成的岗位，上海/北京各 6 个，4 种岗位标题，各有 24 段长 JD 和结束标记；来源名为“离线合成验收”，不冒充真实招聘平台。搜索没有访问招聘网站；岗位原页统一指向无害的 `https://example.com/`，仅验证原生网页呈现，不作为岗位真实性证据。

| 原生操作 | 实际观察与截图 |
| --- | --- |
| 1162×768：选中“合成 02” | 右侧标题、公司、城市、薪资及 JD 同步变为第 2 项，[非空主流程](evidence/UI34-default-discovery-content.jpg)。 |
| 左侧滚到第 10 项，再滚动右侧 JD 到末尾 | [列表滚动](evidence/UI34-default-discovery-list-scroll.jpg)时右侧保持第 2 项及 JD 开头；[详情滚动](evidence/UI34-default-discovery-detail-scroll.jpg)到第 23/24 段与结束标记时，左侧仍是第 7–10 项。筛选与搜索头部持续可见。 |
| 城市筛选选上海，再清空 | 生产本地重筛结果 12→6→12；界面提示未重新请求招聘网站。[普通筛选弹层](evidence/UI34-default-discovery-filter.jpg)有可滚动城市区和固定完成按钮。 |
| 854×768：列表选“合成 03”，详情→列表→详情 | [详情](evidence/UI34-narrow-discovery-detail.jpg)显示第 3 项长 JD；[返回列表](evidence/UI34-narrow-discovery-list-return.jpg)第 3 项仍选中；再进入详情仍为第 3 项。列表与详情使用单栏切换，未挤成并排窄栏。 |
| 窄窗打开城市与来源弹层 | [城市](evidence/UI34-narrow-discovery-filter.jpg)、[来源](evidence/UI34-narrow-discovery-source.jpg)完整留在工作区内，完成、关闭及来源检查入口可见可操作，关闭后保留结果和选择。 |
| 第 3 项按需打开岗位原页，再返回工作区 | [原生 Example Domain](evidence/UI34-narrow-browser-page.jpg)完成加载；[返回工作区](evidence/UI34-narrow-browser-return.jpg)仍显示第 3 项详情。没有重新检索或自动投递。 |
| 原生窗口缩放、打开左侧城市弹层，再恢复普通窗口 | [宽窗恢复](evidence/UI34-browser-width-restored.jpg)同时显示已选第 3 项和已加载网页；[左侧弹层](evidence/UI34-browser-filter-restored.jpg)未遮挡右侧网页；[恢复 1162×768](evidence/UI34-default-browser-restored.jpg)后网页内容仍可见，岗位工作区按可用宽度切换列表/详情。宽窗截图为 1327×768。 |

工具观察中出现过焦点变动及截图暂留旧帧，重新取得原生窗口状态后核对了上表最终可见结果；未把中间旧帧或仅 AX 文本当作截图通过。临时验收应用已从原生菜单退出，用户普通实例保持运行。此次未确认需修改生产代码的缺陷。仍不替代智联等平台登录后列表、JD 和网站续页的真实接入验收。
