# D02 审查修复复核包

日期：2026-09-18。实际目录：`/Users/russeell/Documents/开源项目开发/jobfindsme`。基线仍为 `d720f37f57444b2b03c640d9c12032992e09b15c`，目标为当前未提交工作区。

本轮只复核 `D02-review.md` 四项发现的处理，不重复审查 D01 或后续功能，不联网、不访问账号/简历/密钥、不修改代码。

## 精确差异

1. `main/python-service.ts`：增加启动/停止 promise 和取消标志；在 health 前等待 `spawn`；监听 `error/exit`；消费管道并限定 stderr；SIGKILL 后等待真实 exit；就绪后异常退出上报断开。
2. `main/index.ts`：`before-quit` 无条件进入单一 `shutdownPromise`，启动竞态中也会等待 stop；服务状态清除 client 并发到 renderer。
3. `preload/index.ts` + `shared/contracts.ts` + `renderer/src/App.tsx`：仅增加固定服务状态读取/订阅通道，未暴露任意 IPC；UI 不再在服务退出后显示已连接。
4. `desktop_api/app.py`：设置 `openapi_url=None`。`test_app.py` 增加无令牌 OpenAPI 404 断言。
5. `tests/python-service.test.mjs`：新增端口预留退出、health 前并发停止、真实 spawn ENOENT、SIGKILL 后等待 exit、就绪后异常退出五个回归。`package.json` 保证 Node 测试前先编译被测实现。

## 文件 SHA256

- `apps/desktop/main/index.ts` `b074fe13c34a343fbc99ed2d6d14bb9c52c983e815e1a78cab259a21428bc8a2`
- `apps/desktop/main/python-service.ts` `b3d28b27b6778f4eb62e5f8e904dcb9200c42fa9135438916809c41aad464adc`
- `apps/desktop/preload/index.ts` `ff78b910ef395ecb0e494cd09558032cdcdfe38262f3856f71e750bb86f7482a`
- `apps/desktop/shared/contracts.ts` `9a4a021966b832597b2adb2ac74fca377b268a5a989df699940c33541d5a765b`
- `apps/desktop/renderer/src/App.tsx` `d12f336b7f54b25be8abceec482dd313e4c4efd97ccae6bcb77f7bf66f3aabda`
- `apps/desktop/package.json` `886ebd615ef907f40c16d958aa0e5407b17010a3597800549a6e92ec6d361a7a`
- `apps/desktop/tests/python-service.test.mjs` `6663b58a85fa3bb4b914cabaa15b9846438cab8042a8b07d3d60da513cb5562d`
- `src/jobfindsme/desktop_api/app.py` `4b0092598c4c02f193f614e87bf484542661fdd5dd0f2189d0fc5d68b68df905`
- `tests/desktop_api/test_app.py` `2e1844227d4fb64eb061443acd5c9d99a98996e33f6f872406dc642bedc10d43`

## 已执行的最小验证

- `npm run build`：通过。
- `npm test`：6 passed。
- `uv run pytest tests/desktop_api/test_app.py -q`：3 passed，1 条上游 anyio 弃用警告。
- `ruff check` / `ruff format --check` 针对 desktop API：通过。
- `npm start`：实际窗口显示本地服务已连接；点击关闭窗口后 Electron 进程正常退出。
