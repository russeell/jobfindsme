# D09 隐私与补丁保存/版本冲突有界复核

日期：2026-09-18。审查角色：当前阶段实施者在修改 D09 业务文件前完成的有界只读复核；这不是第二个独立审查会话，也未重复 D03/D08 的全面审查。

## 审查定位与范围

- 基线 commit：`d720f37f57444b2b03c640d9c12032992e09b15c`。
- 审查包：`docs/desktop/evidence/D09-review-request.md`。
- 审查包列出的 8 个 SHA-256 与当前工作区逐项一致；其中 `src/jobfindsme/privacy.py` 是 tracked 修改，其余 D09 目标文件为未跟踪实现，因此结论定位到审查包哈希而不是仅定位到 HEAD。
- 只读检查了 `resume_editor/prompt.py`、`resume_editor/service.py`、`privacy.py`、本地 API 的 D09 路由、Electron 主进程凭据/取消桥、共享契约、迁移及对应 D09 测试。未使用真实简历、API Key、登录或网络服务，未跑全量测试。

## 发现

### [高] 可选 JD 被当作候选人事实，能绕过未知成果阻断

- 证据：`src/jobfindsme/resume_editor/prompt.py:346-347` 将完整可选 JD 放入 `evidence["jd:1"]`；`prompt.py:413-443` 只要求补丁引用一个存在的证据 ID，并把所引用证据文本视为新增数字、技术词和成果词的支持文本。
- 触发：JD 写有候选人简历中不存在的技能、指标或成果（例如 `Java`、`提升 40%`），模型把这些内容写入补丁并引用 `jd:1`。校验器会认定这些词已被证据支持，补丁可直接采纳。
- 影响：外部且明确标记为“不可信参考文本”的 JD 反而可以充当候选人事实，违反“只根据用户确认事实改写、未知成果标为待补充”的验收边界。
- 最小修复：JD 继续作为岗位措辞参考发送给模型，但不得进入可引用的候选人事实映射；只允许当前简历和用户明确确认的项目事实生成 evidence ID。增加一个 JD 含新增技能/指标时仍被阻断的确定性用例。

### [中] 保存新版本与关闭编辑会话不是原子操作

- 证据：`src/jobfindsme/resume_editor/prompt.py:281-294` 先调用 `ResumeEditorService.save_edit()`；该方法在 `resume_editor/service.py:77-134` 自己的数据库连接中提交新 current 版本。之后代码才开启另一个连接把 session 标为 `saved`。
- 触发：新版本事务已经提交后，第二次连接/更新失败或进程在两步之间退出。
- 影响：API 可向用户返回失败，但数据库已经产生新 current 版本；session 仍为 `active`，再次保存会因基础版本不再 current 而永久报版本冲突。用户难以判断是否已保存，也不能正常从该会话重试。
- 最小修复：在一个 `BEGIN IMMEDIATE` 事务中重新确认 session 仍 active、基础版本仍 current、创建新版本并把 session 标为 saved；任何一步失败都整体回滚。增加注入第二步失败的回滚用例，并保留既有 stale-base 冲突用例。

## 已确认边界与限制

- 默认发送路径会在 Electron 主进程读取 Key，并对模型 prompt 整体调用 `create_analysis_copy`；Key 不进入 renderer 持久化。取消只能停止本地等待，无法撤回服务商已收到的请求，现有 UI 已明确说明。
- 基础版本正常变化时，既有保存路径会拒绝 stale base；问题在于保存动作自身跨两个事务，而不是缺少普通冲突检查。
- 规则脱敏只能覆盖结构化标签和常见格式，无法证明识别任意自然语言姓名；产品已在预览限制中说明这一点。本次未把该固有限制升级为新增缺陷。
- 本报告仅覆盖新的模型发送隐私与补丁保存/版本冲突边界；未审查真实服务商行为、付费调用、D03/D08 全量范围或无关桌面功能。

## 实施者处理结果（审查阶段之后）

- 两项发现均核实有效并修复。可选 JD 仍作为不可信岗位参考进入上下文，但不再生成候选人事实 evidence ID；只有当前简历与用户明确补充的项目事实可作为补丁证据。
- `ResumeEditorService` 增加调用者事务内创建版本的内部边界；Prompt 保存使用 `BEGIN IMMEDIATE`，在同一事务内重查 active session、读取 accepted patches、推进 current 版本并关闭 session。第二步失败会整体回滚。
- 新增回归覆盖：JD 引用不能支持新增候选人技能/指标；session 关闭触发器失败时不产生新版本且 session 保持 active。既有 stale-base 冲突继续通过。
- 最小复验：`uv run pytest -q tests/resume_editor/test_prompt.py tests/security/test_analysis_copy.py` → `8 passed`；受影响 Python ruff check/format check 通过。
- 本段是原实施者对报告发现的修复记录，没有另起或声称完成第二轮独立审查。
