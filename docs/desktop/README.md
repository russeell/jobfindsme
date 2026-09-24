# 桌面端开发

JobFindsMe 当前产品是本地桌面工作台：找工作、阅读招聘原页、岗位研究；简历只辅助检索。项目状态见 [当前交接](HANDOFF.md)，模块边界见 [项目结构](STRUCTURE.md)，机器可读的未完成项见 [任务清单](tasks.json)。

开发从仓库根目录安装 Python 依赖，再进入 `apps/desktop/` 安装 Node 依赖。常用检查：

```bash
python -m pytest
cd apps/desktop && npm ci && npm run build && npm test
```

只按改动范围运行必要检查；打包和真实来源验证另行记录。任何来源都要区分“网页可打开”和“岗位列表、分页、完整 JD 可自动读取”。真实投递、付费模型调用以及用户会话数据不纳入自动验收。

旧重构计划、逐任务截图和验收笔记保留在 [历史提交](https://github.com/russeell/jobfindsme/tree/a3a714e17ea73adabd54d36821c46ebc8a924461/docs/desktop) 中，不再占用当前产品文档目录。
