# D02 独立 AI review

日期：2026-09-18。结论：发现 1 项高严重性、2 项中严重性和 1 项低严重性问题；D02 不宜在未处理前维持“通过”结论。

## 发现

### [高] 启动就绪前退出会遗留 Python API 子进程

- 位置：`apps/desktop/main/index.ts:52-56`，`apps/desktop/main/python-service.ts:42-63`
- 触发条件：Python 子进程已经由 `spawn()` 启动，但 `waitUntilReady()` 尚未返回时，用户或系统发出 `SIGINT`/`SIGTERM` 或其他退出请求。此时 `apiClient` 仍为 `undefined`，`before-quit` 在第 53 行直接返回，不会调用 `pythonService.stop()`。Unix 不会因父进程退出自动终止该子进程，因此会留下仍持有启动令牌并打开数据库的本地 API 进程。代码专门安装了这两个信号处理器，所以这不是仅理论上的路径。
- 影响：违反“桌面退出正确管理 Python 进程”的核心验收；用户认为应用已退出时，后台服务仍可存活。
- 最小建议：不要用 `apiClient` 是否赋值作为“有无子进程”的判据。让 `PythonService.stop()` 在未启动时保持幂等，并在每次 `before-quit` 中等待它；同时用单一 shutdown promise 防止重复退出事件绕过等待。增加一个“子进程已 spawn、health 未就绪时退出”的离线用例。

### [中] `spawn` 失败会绕过启动错误处理并崩溃主进程

- 位置：`apps/desktop/main/python-service.ts:42-59`
- 触发条件：默认 `.venv/bin/python` 不存在、无执行权限，或 `JFM_PYTHON` 指向无效文件。Node `spawn()` 会在 `ChildProcess` 上异步发出 `error`，但实现没有注册 `error` 监听器；它不会变成 `pythonService.start()` 可被 `index.ts:42-49` 捕获的 rejection。
- 实证：用本机 Node 22 执行最小离线 `spawn("/definitely/missing-jobfindsme-python")` 样例，结果为 `Unhandled 'error' event` 并以状态 1 退出，与当前缺少监听器的路径一致。
- 影响：常见的本地环境缺失会导致 Electron 主进程未捕获崩溃，而不是受控失败和清理。当前启停测试只使用已存在的 `sys.executable`，拦不住这个回归。
- 最小建议：在 `spawn()` 后立即注册一次性 `error` 监听器，将错误并入启动就绪 promise，清空内部状态并 reject `start()`；测试无效可执行路径时主进程受控退出且无遗留进程。

### [中] `/openapi.json` 绕过 Bearer 鉴权

- 位置：`src/jobfindsme/desktop_api/app.py:96-107`
- 触发条件：任意本机进程在不带 `Authorization` 头时请求 `/openapi.json`。`docs_url=None` 和 `redoc_url=None` 只关闭文档 UI，FastAPI 的 OpenAPI 路由仍默认开启，而鉴权 dependency 只挂在 `/health` 和 `/v1/bootstrap` 上。
- 实证：对当前 `create_app()` 做最小离线 TestClient 探针，无令牌 `GET /openapi.json` 返回 200，同条件 `GET /health` 返回 401。
- 影响：当前泄露的主要是路由和 schema，未直接返回用户数据；但它已违反 D02 证据中“所有当前路由需 Bearer 令牌”的边界，且会随后续敏感 API 增长而暴露完整接口面。
- 最小建议：此桌面 API 不需要 OpenAPI 时，在 `FastAPI(...)` 中同时设置 `openapi_url=None`；如果保留，则将鉴权改为 app/router 级 dependency 并显式验证该路由。补一个枚举所有已注册路由的无令牌检查，避免新路由忘记加 dependency。

### [低] Python 服务就绪后退出不会更新桌面状态

- 位置：`apps/desktop/main/python-service.ts:61-64`，`apps/desktop/main/index.ts:37-48`，`apps/desktop/renderer/src/App.tsx:18-29,45-48`
- 触发条件：`start()` 成功后 Python 因异常、外部终止或资源问题退出。主进程未监听就绪后的 `exit`/失败事件，renderer 又只在挂载时读取一次 bootstrap。
- 影响：若 bootstrap 已成功，界面会继续显示“本地服务已连接”和旧来源状态；后续 IPC 才会以 fetch 错误失败。当前 D02 UI 操作很少，所以严重性较低，但这个底座会让后续页面误报可用。
- 最小建议：由 `PythonService` 向主进程报告就绪后的非预期退出，清除 `apiClient`，并通过受限状态通道让 renderer 显示断开/可重试状态；至少增加一个就绪后子进程退出的离线用例。

## 范围与限制

- 已核对 `D02-review-request.md` 中所列核心文件 SHA256 与 `D02-review.diff` 哈希，审查时与审查包一致。
- 检查了 tracked diff、D02 验收/证据，以及列入包内的 Electron 主进程、preload、共享契约、renderer、FastAPI 和针对性测试。
- 未重跑已记录通过的全部测试/构建；只运行了上述 OpenAPI 无令牌探针和 Node `spawn` 失败最小样例。
- 未访问网络、真实账号、密钥、简历或外部模型；未验证后续 WebContentsView、平台会话、打包后 Python 分发或真实来源接入，这些不在 D02 审查范围。
- 本报告仅写入 `docs/desktop/evidence/D02-review.md`，未修改业务代码、任务状态或其他证据。
