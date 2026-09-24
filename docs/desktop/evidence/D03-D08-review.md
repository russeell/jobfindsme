# D03/D08 独立只读 AI review

日期：2026-09-18。基线 commit：`d720f37f57444b2b03c640d9c12032992e09b15c`。

## 审查定位与结论

- 已逐项重算 `D03-D08-review-request.md` 中 20 个 SHA-256；全部与共享工作区当前文件一致，HEAD 也与审查包基线一致。
- 已阅读 tracked diff、新增文件、D03/D08 证据、相关迁移/服务/API/Electron/renderer 实现及针对性测试。没有访问真实简历、账号、密钥或模型服务，也没有联网、提交、发布或修改任务状态。
- 共发现 7 项：2 项高严重性、5 项中严重性。迁移增量性、简历确认事务回滚、三协议基本请求/响应与用量映射、唯一 `desktop-v3` UI 基线未发现额外阻塞缺陷；限制见文末。

## 发现

### 1. 高：取消只中断主进程到回环 API 的 fetch，实际模型请求仍继续，最终状态可覆盖 `cancelled`

- 位置：`apps/desktop/main/index.ts:112-133`、`src/jobfindsme/desktop_api/app.py:411-455`、`src/jobfindsme/models/gateway.py:99-128`。
- 触发：连接测试开始后点击取消。Electron 的 `AbortController` 只传给 `DesktopApiClient`，Python 端创建模型请求时没有 `CancellationToken`；取消端点仅把数据库状态写成 `cancelled`。已经在线程中执行的 `urllib` 请求不会停止，稍后仍会在测试端点的正常返回路径写成 `verified`，或在异常路径写成 `failed`。反向竞态也可能在成功后被迟到的取消请求改成 `cancelled`。
- 离线复现：对同一连接依次调用 `record_test(...CANCELLED...)` 和模拟迟到请求的 `record_test(...VERIFIED...)`，最终状态为 `verified`。代码中没有 test/run id 或条件更新阻止迟到结果。
- 影响：用户取消后仍可能继续向外部端点发送/等待并产生用量，且界面与持久状态误报；不满足 D08 的取消状态契约。
- 最小修复：为每次测试生成 `test_id`，服务端保存活动请求及取消令牌；取消端点取消对应活动 transport，并以 `test_id + 当前状态` 条件更新，忽略旧请求的迟到完成。主进程捕获局部 controller/id，只在仍为本次测试时清理；renderer 应采用取消响应。若保留同步 `urllib`，需换成可真正取消的 transport，或明确取消仅为“停止等待”且禁止迟到结果覆盖，但这仍不能满足停止外部请求的当前承诺。

### 2. 高：直接超时会在错误处理自身抛出 `AttributeError`，连接状态不会记录为失败

- 位置：`src/jobfindsme/models/gateway.py:117-127`、`src/jobfindsme/desktop_api/app.py:431-436`。
- 触发：`urlopen` 或响应读取直接抛出 `TimeoutError`。联合异常分支无条件读取 `error.reason`，但 `TimeoutError` 没有该属性，因此实际抛出 `AttributeError`；API 只捕获 `ModelGatewayError`，会返回未处理的 500，连接保留旧状态。
- 离线复现：mock `urllib.request.urlopen` 抛 `TimeoutError("timed out")` 后调用 `UrllibJsonTransport.post`，实际得到 `AttributeError: 'TimeoutError' object has no attribute 'reason'`。
- 影响：D08 明确要求的超时状态不可见，且 renderer 得到泛化服务错误而非安全、确定的失败状态。
- 最小修复：分别捕获 `TimeoutError` 并转换为不含 URL/密钥的固定 `ModelGatewayError("model endpoint timed out")`；`URLError` 的原因也应归一化而非原样持久化。增加 transport 直接超时和 API 最终 `failed` 状态两个离线断言。

### 3. 中：连续上传两个简历后确认最新一个，较早 draft 会永久保持检索门禁，但 UI 无恢复入口

- 位置：`src/jobfindsme/desktop_api/app.py:278-305`、`apps/desktop/renderer/src/App.tsx:52-61`。
- 触发：先上传 A，不确认；再上传 B 并确认 B。状态查询以“工作区是否存在任意 draft”作为门禁，因此 A 仍使 `search_profile_state` 为 `pending_confirmation`。renderer 只保留当前进程内最后一次上传返回的 `draft`；刷新后既不能列出、打开、放弃，也不能取回 A。
- 离线复现：TestClient 连续导入内容为 `Python` 与 `Docker` 的两个 TXT，只确认第二个；确认返回 200 且已有 `current_version_number=1`，但返回状态仍为 `pending_confirmation=true`、`search_profile_state=pending_confirmation`。
- 影响：正常的“选错文件后重新上传”操作会把后续检索永久锁住，只能绕过 UI 清库或继续调用隐藏 ID，门禁契约不可恢复。
- 最小修复：定义单一 active pending import：新上传可显式 supersede 旧 draft，或状态响应返回待确认 profile 列表/active id，并提供恢复核对与放弃入口。门禁只绑定 active pending；增加“两次上传、确认/放弃最新项后可解除门禁”的 API/UI 契约样例。

### 4. 中：分析预览 API 在省略脱敏字段时默认不脱敏，与“默认过滤”安全边界相反

- 位置：`src/jobfindsme/desktop_api/app.py:95-98`、`src/jobfindsme/desktop_api/app.py:359-375`、`src/jobfindsme/privacy.py:37-53`。
- 触发：调用 `/v1/resumes/analysis-preview` 时只传 `workspace_id`。请求模型把缺省值变成空列表，API 再显式传入空集合；这绕过 `create_analysis_copy` 中 `None => 全部字段` 的安全默认。
- 离线复现：确认包含 `me@example.com` 的版本后省略 `redacted_fields`，接口返回 200、`redacted_fields: []`，正文仍包含完整邮箱。
- 影响：当前 renderer 总会传字段列表，但回环 API 和后续 D09 模型调用复用此边界时会 fail-open；调用方遗漏参数即可产生未脱敏副本。
- 最小修复：API 缺省值改为 `None` 并传递给脱敏函数；“明确保留身份字段”使用单独的显式 consent/mode 字段，不能与参数遗漏共用空列表语义。增加“省略字段默认全过滤”和“显式 keep 才不过滤”测试。

### 5. 中：脱敏正则同时存在常见漏脱敏和业务内容误删

- 位置：`src/jobfindsme/privacy.py:20-27`。
- 触发与离线结果：`电话：138-0013-8000` 和 15 位旧身份证号保持原文；`项目名字：智能招聘系统` 被改为 `项目[已过滤:name]`；`项目地址：https://github.com/acme/repo` 被改为 `项目[已过滤:address]`。
- 影响：发送副本可能泄露常见格式的手机号/证件号，同时误删项目名称与代码仓库 URL，降低后续匹配和简历修改的事实准确性。现有测试只覆盖连续 11 位手机号、18 位身份证、带标签姓名/地址的窄样例。
- 最小修复：优先从结构化 basic-information 字段脱敏；文本兜底规则应锚定独立字段标签/行首，避免匹配“项目名字/项目地址”。手机号先规范可接受的空格/连字符再识别，证件类型明确覆盖范围；补充上述四个边界样例，并在无法可靠识别时让预览明确提示规则范围。

### 6. 中：修改已有连接时先提交非秘密配置、后写密钥；密钥写入失败会把旧密钥绑定到新端点

- 位置：`apps/desktop/main/index.ts:102-110`、`apps/desktop/main/secure-secret-store.ts:17-26`、`src/jobfindsme/models/gateway.py:230-248`。
- 触发：编辑已有连接，同时更换端点和 API Key；数据库更新成功后，密钥文件因损坏、权限或磁盘错误写入失败。IPC 抛错，但数据库已提交，新密钥未保存，旧 connection id 下的旧密钥仍在。重新打开页面会显示新端点且 `has_api_key=true`，测试时会把旧密钥发送给新端点。
- 影响：跨存储部分失败造成凭据误投递；`writeFileSync` 直接覆盖也可能在中断时破坏整份密钥文件。
- 最小修复：采用 staged/two-phase 更新：先原子写临时密钥文件并 fsync/rename，再切换配置版本；失败时保留旧配置与旧密钥的配对。至少在密钥写失败时回滚数据库配置或删除该连接的可用标记，并测试已有连接的写失败路径。

### 7. 中：Gemini API Key 被拼入 URL 查询串，扩大密钥进入 URL 日志/遥测的暴露面

- 位置：`src/jobfindsme/models/gateway.py:336-341`。
- 触发：任何 Gemini 测试请求。代码将完整 key URL 编码后放入 `?key=`；虽然当前 HTTP 错误文案不回显响应正文，但 URL 更容易被代理、调试器、网络错误遥测或上游访问日志记录，且现有测试没有断言密钥不出现在 URL。
- 影响：与“密钥经最小通道提供、日志脱敏”的目标不一致；错误正文脱敏不能覆盖 URL 侧记录。
- 最小修复：协议支持时改用专用认证 header；若必须使用查询参数，则需在 transport 层禁止/净化 URL 日志与异常，并对所有错误路径加“异常、状态、日志均不含 key”的契约测试。

## 未发现缺陷的核对项

- **简历版本事务原子性**：`confirm_profile` 对事实状态、profile 确认、旧 current 清除与新版本插入使用同一 `Database.connect()` 事务；新版本插入/唯一约束失败会整体回滚，没有发现“旧 current 已清除但新 current 未落盘”的部分提交路径。SQLite 唯一索引也限制每工作区仅一个 current。并发确认的最终胜者取决于锁顺序，但串行化后版本号与 parent 链保持完整；本次未做进程崩溃注入。
- **0014/0015 迁移**：两份迁移只创建新表和索引，不更新或删除既有 workspace/source/profile/fact 数据；现有迁移器把整轮迁移置于事务内，旧数据保留样例与实现一致。兼容性检查主要比较列签名，未对历史上人工预建同名表的所有约束做等价验证；这不是正常旧数据库升级路径。
- **三协议基本映射**：OpenAI 兼容、Anthropic、Gemini 的最小请求路径、响应文本与已覆盖用量字段映射和当前离线样例一致。没有真实调用，因此服务商方言、SSE 流、实际配额/错误形态仍未验证。
- **错误回显**：HTTP 错误正文未直接持久化或返回；模型连接响应不含 API Key。除发现 2、7 外，未看到数据库、renderer 持久化或显式日志写入明文 Key 的路径。
- **UI 基线**：`docs/desktop/ui/README.md` 明确唯一基线为 `desktop-v3`；当前 renderer 延续其两组导航、灰白配色、156px 侧栏、25/22px 内容间距、双栏工作区、760px 模型设置宽度与简历步骤结构。未发现转用旧绿色版或 `neutral-v2` 的证据；本次未扩展为审美重设计。

## 审查限制

- 只运行了针对发现的临时 SQLite/TestClient/注入式离线样例；未重复已经与当前哈希绑定并通过的 33 项测试、ruff、前端构建和 Node 生命周期检查。
- 未访问网络、真实招聘会话、真实简历/密钥或真实模型；协议实服兼容性、安全存储在不同操作系统的行为、真实 socket 取消能力仍需后续在授权环境按 D08 证据说明验证。
- 本报告只审查 D03/D08 指定边界；没有复审已通过的阶段 A，也没有评价无关架构或未实现的 D04/D07/D09 功能。
