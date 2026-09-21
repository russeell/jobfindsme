# D09 隐私与补丁边界审查包（未启动审查）

日期：2026-09-18。用途：后续如需独立 AI review，可直接审查以下精确版本；本轮不创建审查会话。

重点边界：全模型发送载荷脱敏、基本信息默认省略、安全凭据只在 Electron 主进程读取、取消传播、模型响应身份字段过滤、事实证据/新增成果阻断、基础版本冲突及编辑会话迁移级联删除。

```text
e58aef0e635a3a2b3f032bd77989cc4654d3e0b2713840f9f038d9a1a88eabd6  src/jobfindsme/resume_editor/prompt.py
9af3c0e81ab449fc46e348de280841f168f209b253eb42608c394ab306b270f4  src/jobfindsme/resume_editor/service.py
43158471f9be7e195b4dd89bc92b95fa6be70109f84bd8df1589896190aeec28  src/jobfindsme/privacy.py
d40082cf4a4e4dc2ccb5493cc79f9d91aa6ac2655acb5a83ae8d79420f939969  src/jobfindsme/desktop_api/app.py
9174ecc2fffb8e46984573ae1936737fa29d6505976907d4f02ea59ab696e25c  src/jobfindsme/migrations/0017_resume_edit_sessions.sql
c62e7f8c386d778f74f5874f9357436f3bc7fe09e957f94ebe10e863fd048fa2  apps/desktop/main/index.ts
f43839f2901a3b5c139029f7016391980f77d73a78d8f349b4cedd4c96b78ed4  apps/desktop/renderer/src/App.tsx
8602a3707cf6262b22a9f7d8f2b046ea792bec74604ace668b10dd34f92a69ac  apps/desktop/shared/contracts.ts
```

已通过的最小复现与验证见 `D09.md`。审查时不得使用真实 API Key 或真实简历，不需要重复 D03/D08 已完成的全面审查。
