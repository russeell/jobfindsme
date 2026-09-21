# D02 独立审查包

实际目录：/Users/russeell/Documents/开源项目开发/jobfindsme
基线：d720f37f57444b2b03c640d9c12032992e09b15c
目标：当前未提交工作区；审查期间冻结上述业务范围。

范围：下列未跟踪文件与 D02-review.diff（tracked diff）。验收见 tasks.json D02，已有检查见 D02.md，不重复全量测试。重点检查 IPC/本地 API 鉴权、令牌暴露、子进程退出与失败恢复、真实状态与来源门禁。

仅可写 docs/desktop/evidence/D02-review.md，其余只读；不访问账号、简历、密钥，不联网调用，不改代码或任务状态，不提交发布。给出有证据的缺陷、严重性、触发条件、行号与最小修复；未发现也说明限制。

## 文件 SHA256

- `apps/desktop/main/api-client.ts` `1da4d7f2961ded1ad3195979ef47c8ba1ba098f0b007817cb7fc943653d21459`
- `apps/desktop/main/index.ts` `7444738b82a4e62b5b6df95b0b84dd9fd33e99f547a2a891544b44b39a35ea96`
- `apps/desktop/main/python-service.ts` `3f08208c49609fb26984a40f431f665acbf9cf006fd2133ba2730d91d3cfc834`
- `apps/desktop/package-lock.json` `12e42feacb5328eb826a6a94f4e1692af91b002743414a545cd23beb85938caa`
- `apps/desktop/package.json` `a95bb19e033793b52af809cd1d7440211f6bd91778a3ad2beeeb94e94479f738`
- `apps/desktop/preload/index.ts` `1a8ebd504c99030a553f03bde9576080cd1be379e89b7a6335d9cb823a7e30e9`
- `apps/desktop/renderer/index.html` `f77250481d914bb8703e1818cafc86a449218f4450e8bb449868bdc30d5bc467`
- `apps/desktop/renderer/src/App.tsx` `247f250ee887dfe0fe3e0fbd45615d71ff11817fd1f67299c7a98620aaccc71c`
- `apps/desktop/renderer/src/env.d.ts` `72f2a2b9e5c482037d975a36ef86952ed57976eb2d823706277c1fac26cd6eed`
- `apps/desktop/renderer/src/main.tsx` `3a79bfb215adc1d2e030482246503df31e53168ede2b6eb3944dfcd68b38cb5b`
- `apps/desktop/renderer/src/styles.css` `738d981304dd68754fadd8c74fa5a124a2349376244f01327fe3022cbe106ef6`
- `apps/desktop/shared/contracts.ts` `3005ea5409e5a5349ca6b18af1a4b8cb0a0db9e1bcbb295e263e0f4aaf9f1638`
- `apps/desktop/tests/source-gates.test.mjs` `1520b86c3cf1303667306f7f7dd55cf91de6f0647862a6a83cc8005e33d971b9`
- `apps/desktop/tsconfig.electron.json` `c5733109c6ab577eee8af4d798eaaf2838be5e426b1a6e99ea75b4bbdda3f6a5`
- `apps/desktop/tsconfig.json` `9ae4c39d6e0693683371e18cdbc8550b3a7fe6ce9ce367eb9fc5e728c36d98c2`
- `apps/desktop/vite.config.mts` `8cebfa72d2a7c7c8780cdb3008a4bb53089fb5933ad48dabb0b968ab6df50776`
- `src/jobfindsme/desktop_api/__init__.py` `ca3b01fb0070fe1344a11c14c8ec65adf2e4bb82eefa5e4b0cb9a91ea54084ef`
- `src/jobfindsme/desktop_api/__main__.py` `6c2148032a6f4e8b93b5267d2fe34e42a83a2ca091c2d1a13a62143747feb2bd`
- `src/jobfindsme/desktop_api/app.py` `b15e4b6625e56ce82f3dc72896bc8c56d1f11a1227ba4c7dbf41ed84ea45bfdf`
- `tests/desktop_api/test_app.py` `6363be3028c950cf774d521c5f037f42c4378a55cbb1c0d9a50df31511ecb59e`

tracked diff SHA256: 362466254d326c97658c6d3a7547f5704817eb586ae9d00419079f5bc1f3c981
