# 桌面端开发

JobFindsMe 当前产品是本地桌面工作台：岗位检索、内嵌浏览器、简历编辑、面试准备与投递记录，复用岗位 JD 和关联简历。项目状态见 [当前交接](HANDOFF.md)，模块边界见 [项目结构](STRUCTURE.md)，机器可读的未完成项见 [任务清单](tasks.json)。

开发从仓库根目录安装 Python 依赖，再进入 `apps/desktop/` 安装 Node 依赖。常用检查：

```bash
python -m pytest
cd apps/desktop && npm ci && npm run build && npm test
```

只按改动范围运行必要检查；打包和真实来源验证另行记录。任何来源都要区分“网页可打开”和“岗位列表、分页、完整 JD 可自动读取”。真实投递、付费模型调用以及用户会话数据不纳入自动验收。

旧重构计划、逐任务截图和验收笔记保留在 [历史提交](https://github.com/russeell/jobfindsme/tree/a3a714e17ea73adabd54d36821c46ebc8a924461/docs/desktop) 中，不再占用当前产品文档目录。

## 可重复打包与实际包验收

发行使用 Python 3.13、Node 22，依赖锁为 `requirements/release.txt`（全依赖及 SHA256）与 `apps/desktop/package-lock.json`（包含固定的 Playwright）。普通推送/PR运行 CI；macOS/Windows包只在手动 dispatch 或版本 tag 时构建，不自动发布 Release。两端必须选择同一提交。

在独立 Python 3.13 环境、仓库根目录安装发行依赖；生产输入先提交，打包会拒绝未提交的输入或过期构建：

```bash
python -m pip install --require-hashes -r requirements/release.txt
python -m pip install --no-deps --no-build-isolation -e .
cd apps/desktop
npm ci
npm run build
cd ../..
python scripts/freeze_desktop_api.py
cd apps/desktop
# macOS；Windows 对应 package-windows.mjs 与 audit-windows-package.mjs
node scripts/package-macos.mjs
node scripts/audit-macos-package.mjs
```

冻结包装器先核对实际安装的依赖版本，再生成Python来源指纹；桌面构建也记录输入指纹。打包与审计核对两者的来源提交、代码和锁摘要，不能靠改 package.json 版本把旧载荷标成新包。`scripts/desktop-build-inputs.json`列出参与构建的输入；新增运行时资源时同步维护。

更新 Python 发行锁需使用 uv（不作为应用依赖），在明确升级范围后重新解析：

```bash
uv pip compile pyproject.toml requirements/release-tools.in --extra dev --python-version 3.13 --universal --generate-hashes --no-header --no-annotate --output-file requirements/release.txt
```

检查锁变更后，执行两端实际包验收。CI只缓存pip/npm下载和上游Electron归档，不缓存用户资料或旧冻结API/应用。`smoke-desktop.mjs`仅用于隔离CI验收：虚构PDF/Word原件 → 编辑/正常和窄窗口 → 保存/草稿重启恢复 → Word/PDF内容样式 → 旧岗位稿/归档原件复用/取消导出。界面、IPC、冻结后端和SQLite均为真实实现，文件框返回虚构路径；不访问招聘、不调用模型、不发送申请。公开发布仍须另行授权，保留校验文件与已通过的构建链接。

本地个人信息不得上传，包括简历与提取内容、账号、对话、草稿、数据库、密钥、登录会话及私人日志/截图；以前的模型测试授权不替代当前限制。双端共用`package-privacy.mjs`拦截数据库及旁路文件、浏览器存储、凭据、误混入的简历和包外链接，仅放行必要技能、许可证及指定依赖资源。完整验收成功后，CI只上传明确命名的ZIP和校验文件，不通配上传日志/截图。仍需审阅源代码和公开资源；文件类型检查不等于任意内容识别。保留用户本机原件与会话，不通过删除用户资料来规避检查。
