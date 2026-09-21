# D10/D11 与跨模块安全有界复核

日期：2026-09-18。范围仅覆盖 D10、D11 与来源 IPC/模型发送边界；未重复全量测试。

## 实际发现

1. D10 的 `WebEvidenceSearch` 只读取 Bing RSS 摘要，却把命中写成 `independently_retrieved`；公司/团队相关性也只在标题和摘要中做字符串判断，RSS 日期被当作评价发布日期。这不能证明正文、公司、团队或日期已核验。
2. 研究模型载荷包含全部公开/用户评价摘录，超出项目改写和面试准备所需；模型返回的字符串直接成为报告内容，没有显式“待用户核实”边界。
3. D11 虽保存 `rule_version_id`，执行时只传筛选和简历版本，`create_snapshot` 会重新选择默认权重；非默认冻结评分没有真正生效。
4. 进程异常退出后，`desktop_task_runs.status='running'` 没有恢复路径，会永久阻止该任务后续执行。Electron 的轮询也没有进程内互斥。
5. 系统通知不受支持时仍立即写 `delivered_at`，导致用户从未看到的通知不可重试。
6. 来源搜索/浏览 IPC 已校验 `event.sender === mainWindow.webContents`；远程来源视图无 preload、Node 集成关闭、启用 sandbox。新增动作桥继续沿用该边界，没有发现远程页直取本地权限的路径。

## 处置

- 以上 1–2 由 D10a 修复，3–5 由 D11a 修复；6 作为 D04c 的回归约束。
- 旧 D10/D11 证据仍保留历史原貌，本文件记录其结论被修正的原因，不篡改原始会话记录。

## 差异标识

- `research/service.py`：`ef9e3997eaaf9b45c9077a67b1b3ac4cefb9842c0ca015641363ee1116127743`
- `scheduler/service.py`：`1e7a3080f82c009b372601d7386a10338beb6ec8aca98cb7d7c02fd32ad1745b`
- `desktop_jobs.py`：`4dd5b8744bd899fb0f1fb7528c5f73e907057d1156e78c3991ab5a0e9d464828`
- `apps/desktop/main/index.ts`：`00fe38b63a81542edeafc15e4f3e67b62fff78835533733956f8740309af8545`

仓库基线中的桌面文件多数仍为未跟踪文件，因此以上完整文件 SHA-256 比只包含 tracked 文件的 `git diff` 更能标识本轮实际内容。
