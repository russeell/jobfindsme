# D03/D08 独立审查处理记录

日期：2026-09-18。对应审查：`D03-D08-review.md`。结论：7 项均核实并修复，无降低验收标准的例外。

## 处理映射

1. **取消竞态**：每次测试创建唯一 `test_id`，`model_test_runs` 保存状态；回环 API 注册活动 `CancellationToken`，取消会关闭正在等待的 HTTP(S) connection。终态只能从本 test_id 的 `testing` 条件更新，旧运行迟到结果不能覆盖新运行。桌面主进程用局部 controller/id 清理，取消后重读真实状态。界面明示：若服务商已收到请求，取消仍可能产生用量。
2. **超时异常**：`TimeoutError` 单独归一为固定的 `model endpoint timed out`，不再读取不存在的 `reason`；其他 socket 错误不持久化 URL 或密钥细节。
3. **active draft 恢复**：`active_resume_imports` 每工作区只指向一个当前待确认导入；新上传显式 supersede 旧 active draft。状态 API 返回可恢复的 draft，刷新后可继续核对，也可“放弃本次导入”解除门禁；旧 draft 数据不被破坏。
4. **默认脱敏**：分析预览省略配置时传 `None`，默认过滤全部身份类型；仅 `privacy_mode=keep` 表示用户明确保留，renderer 在用户取消全部勾选时使用该显式模式，不增加重复弹窗。
5. **脱敏边界**：手机覆盖空格/连字符，身份证覆盖 15/18 位；姓名/地址标签改为独立行首锚定，不再误删“项目名字”和“项目地址”。预览显示规则局限，要求发送前检查。
6. **配置/密钥配对**：新 Key 先以新 `credential_ref` 原子写入临时文件，`fsync + rename`后再提交配置。密钥写入失败不修改配置；配置失败清理新暂存密钥。端点/协议/模型/服务商改变却未提供新 Key 时清除旧凭据配对，不将旧 Key 发给新端点。
7. **Gemini 认证**：改用 `x-goog-api-key` header，URL 不再包含 Key；契约样例断言所有协议 URL 不含测试密钥。

## 针对性验证

- Python：41 passed，1 deselected（既有子进程回环 bind 项受沙箱限制）。覆盖 active draft 覆盖/恢复/放弃、缺省脱敏/显式 keep、手机/证件/项目标签、直接超时、test_id 迟到结果、真实取消令牌、API failed/cancelled 终态、Gemini header 与路由变更解绑旧凭据。
- `ruff`：受影响 Python 文件通过。
- Desktop：typecheck/生产构建通过；Node 8 passed，新增密钥暂存失败不改配置、配置失败清理新暂存凭据。
- 未调用真实模型，未读取其他应用密钥，未改变 desktop-v3 视觉基线。

## 修复后精确 SHA-256

```text
e88c45325ec626cf4ba57f11f33c54da19dfa41a1253900b19eb1bc84c4b9473  src/jobfindsme/migrations/0016_stage_b_review_fixes.sql
da784ca97cb5094e48a6be3a1d3a22a89203630a6b5123e78b303594741a7ad0  src/jobfindsme/profiles/service.py
abf231ec3997c24403d7e01d4a2289a16e07ac58da52a26dd550bb70618685a9  src/jobfindsme/privacy.py
ebfab88ec5f5ca0967e62eb982686bee2541a1cd1aa88c7136f4d955081b1977  src/jobfindsme/models/gateway.py
c6c2ed10e455dd9e2708564637594840ea9057691566028d56f0ec793e96b2ff  src/jobfindsme/desktop_api/app.py
c3c3eaa7f2a9c9dfc254d4a7df1951679be6a165f1cd9e671de250c8ce34a28d  apps/desktop/main/api-client.ts
027af777d10ce7b78c27cd0ed94c8f5bd6113b821d3fcb3fda1964eb3b695068  apps/desktop/main/index.ts
c708439911364887bc21f03f0327b761028e0fd177e0076916e0764af0b9f762  apps/desktop/main/model-connection-service.ts
4bb4297ae4b792fdc4281eba4c0d87a15eca8036cb0033ea3d033b176dccd900  apps/desktop/main/secure-secret-store.ts
e8c5fa6855cf2c6bc6a64ea65fa83ce352c9983b58c254f69be542b9179b50d9  apps/desktop/preload/index.ts
7835d3c40189d322d051e584d8997148285e080eb8364ce7585873664dd3c2df  apps/desktop/shared/contracts.ts
29cf35fc62040acb572b85b7c9862deb2a9a6c8da12f90c7ee3c183b846fb699  apps/desktop/renderer/src/App.tsx
a83457a4d1add9966bb99ab673d526a257b1c1e3a16e105e3bced533dbc0d25e  tests/profiles/test_resume_migration.py
ac6a9e418bb9e53a2b85b61a9989d19c4bdb1a5de7297bcbc382a227135fd557  tests/security/test_analysis_copy.py
3c1d2eb2e22a3c924e8a68d2df23400ea260c316f2980f3cd27d58d4239740f4  tests/models/test_gateway.py
4c7dc982d77c854662eac04ca2c51bfaee27e5fdf1316ae9aa99194d64ea7c49  tests/desktop_api/test_app.py
440e23c6138bed392376c983b9c333b4b962b8793efb3c4a4367f88cda97f5f8  apps/desktop/tests/model-connection-service.test.mjs
```

限制：关闭本地 transport 可停止客户端继续等待/读取，但无法撤回已经到达服务商的请求，也不能保证不计费；UI 已如实提示。
