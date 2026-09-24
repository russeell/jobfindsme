# D02 独立审查处理记录

日期：2026-09-18。结论：`D02-review.md` 的四项发现已核实并处理。原审查报告保留不变。

| 发现 | 处理 | 回归证据 |
| --- | --- | --- |
| 启动就绪前退出留下子进程 | `PythonService` 使用 `stopRequested/startPromise/stopPromise` 统一协调；端口预留时退出不再 spawn，health 等待时退出会终止并等待子进程；主进程不再用 `apiClient` 判断是否需清理，重复退出共用单一 promise。 | Node: `stop during port reservation...` 和 `stop is idempotent while health is not ready`。 |
| spawn 失败绕过捕获 | 启动先等待 `spawn`，并将 `error/exit` 合并到启动失败 promise；无效 Python 路径现在受控 reject，不会触发 unhandled error。 | Node: `spawn errors reject start...` 使用真实缺失可执行路径。 |
| `/openapi.json` 未鉴权 | 桌面 API 无需公开 schema，设置 `openapi_url=None`。 | Python: 无令牌 `/openapi.json` 返回 404，`/health` 仍返回 401。 |
| 就绪后服务退出仍显示已连接 | 服务就绪后非预期 `exit` 清除 client，通过固定的 `desktop:service-status` 通道通知 renderer；UI 显示断开原因。 | Node: `unexpected exit after readiness reports a disconnected status`。 |

额外生命周期约束：主进程消费子进程 stdout，stderr 只保留最后 8 KiB 用于受控启动错误；SIGTERM 超时后发出 SIGKILL，随后仍等待 `exit`，超时则显式报错。

验证结果：`npm run build` 通过；`npm test` 6 passed；`pytest tests/desktop_api/test_app.py -q` 3 passed（一条上游 anyio 弃用警告）；Electron 实际启动后显示本地服务已连接，点击窗口关闭后进程正常退出。
